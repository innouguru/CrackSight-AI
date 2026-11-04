import { ArrowLeft, ArrowRight, Camera, CloudUpload, FileImage, RotateCcw, X } from 'lucide-react'
import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Brand } from '../components/Brand'
import { DemoNotice, SafetyNotice } from '../components/Ui'
import { useGuestSession } from '../hooks/useGuestSession'

const structureTypes = [
  { value: 'wall', label: 'Wall' },
  { value: 'beam', label: 'Beam' },
  { value: 'column', label: 'Column' },
]

const MAX_FILE_SIZE_MB = 10
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp']

interface SelectedImage {
  file: File
  dataUrl: string
  dimensions: [number, number]
}

function readImage(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      if (typeof reader.result === 'string') resolve(reader.result)
      else reject(new Error('Could not preview this file.'))
    }
    reader.onerror = () => reject(new Error('Could not read this file. Try another image.'))
    reader.readAsDataURL(file)
  })
}

function getImageDimensions(source: string) {
  return new Promise<[number, number]>((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve([image.naturalWidth, image.naturalHeight])
    image.onerror = () => reject(new Error('This image could not be decoded. Choose a valid JPEG, PNG or WebP file.'))
    image.src = source
  })
}

export function GuestAnalysisPage() {
  const {
    isLoading,
    error: sessionError,
    createSession,
    clearSession,
    photograph,
    analysis,
    isUploading,
    isAnalysing,
    uploadError,
    analysisError,
    uploadPhotograph,
    analysePhotograph,
    analysesRemaining,
    isSessionValid,
  } = useGuestSession()

  const [selectedImage, setSelectedImage] = useState<SelectedImage | null>(null)
  const [structureType, setStructureType] = useState('wall')
  const [dragging, setDragging] = useState(false)
  const [sessionExpired, setSessionExpired] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const cameraRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    void createSession()
  }, [createSession])

  async function chooseFile(file?: File) {
    setSelectedImage(null)
    setValidationError(null)
    if (!file) return

    if (!ALLOWED_TYPES.includes(file.type)) {
      setValidationError('Choose a JPEG, PNG or WebP image.')
      return
    }

    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      setValidationError(`This image is larger than the ${MAX_FILE_SIZE_MB} MB limit. Choose a smaller file.`)
      return
    }

    try {
      const dataUrl = await readImage(file)
      const dimensions = await getImageDimensions(dataUrl)
      setSelectedImage({ file, dataUrl, dimensions })
    } catch (err) {
      setSelectedImage(null)
      setValidationError(err instanceof Error ? err.message : 'Could not preview this image.')
    }
  }

  function onInputChange(event: ChangeEvent<HTMLInputElement>) {
    void chooseFile(event.target.files?.[0])
    event.target.value = ''
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setDragging(false)
    void chooseFile(event.dataTransfer.files[0])
  }

  async function handleUpload() {
    if (!selectedImage) return
    setValidationError(null)
    try {
      await uploadPhotograph(selectedImage.file, structureType)
    } catch {
      // Error is already set by the hook.
    }
  }

  async function handleAnalyse() {
    if (!photograph?.photograph_id) return
    try {
      await analysePhotograph(photograph.photograph_id)
      if (analysis) {
        navigate('/try/results', {
          state: {
            photographId: photograph.photograph_id,
            structureType: photograph.structure_type,
            fileName: selectedImage?.file.name ?? '',
            imageSize: selectedImage?.dimensions,
          },
        })
      }
    } catch {
      // Error is already set by the hook.
    }
  }

  const usedAnalyses = 3 - analysesRemaining

  return (
    <div className="upload-page">
      <header className="upload-header">
        <Link to="/"><Brand /></Link>
        <div className="upload-header__right">
          {isLoading ? (
            <span>Establishing guest session…</span>
          ) : (
            <>
              <span>
                Guest session · {isSessionValid ? 'active' : 'expired'} · {analysesRemaining} analyses remaining
              </span>
              <Link className="button button--secondary" to="/sign-in">Sign in</Link>
            </>
          )}
        </div>
      </header>
      <main className="upload-main">
        <Link className="upload-back" to="/"><ArrowLeft size={14} /> Back to home</Link>
        <div className="upload-main__heading">
          <p className="eyebrow">Guest analysis</p>
          <h1>Review a building photograph</h1>
          <p>Upload an image to run AI-assisted crack segmentation. Select the structure type and submit for analysis.</p>
        </div>

        {isLoading && <p className="prototype-alert" role="status">Establishing your guest session…</p>}
        {sessionError && <p className="prototype-alert" role="alert">{sessionError}</p>}
        {sessionExpired && <p className="prototype-alert" role="alert">This guest session has expired. Its results are unavailable after 24 hours.</p>}
        {analysesRemaining < 1 && !sessionExpired && !isLoading && (
          <p className="prototype-alert" role="status">No guest analyses remain in this session. Create an account to explore the registered-user screens.</p>
        )}
        {validationError && <p className="prototype-alert" role="alert">{validationError}</p>}
        {uploadError && <p className="prototype-alert" role="alert">{uploadError}</p>}
        {analysisError && <p className="prototype-alert" role="alert">{analysisError}</p>}
        <DemoNotice>
          Real analysis is connected to the backend. Guest sessions are limited to 3 analyses per session and expire after 24 hours.
        </DemoNotice>
        <section className="card upload-card" style={{ marginTop: 14 }}>
          <div className={`dropzone${dragging ? ' is-dragging' : ''}`}
            onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
          >
            <span className="dropzone__icon"><CloudUpload size={21} /></span>
            <h2>Drag a photograph here</h2>
            <p>or browse from your device</p>
            <div className="upload-preview__actions">
              <button type="button" className="button button--secondary" disabled={!isSessionValid || isLoading || isUploading || isAnalysing} onClick={() => inputRef.current?.click()}><FileImage size={15} /> Choose image</button>
              <button type="button" className="button button--secondary" disabled={!isSessionValid || isLoading || isUploading || isAnalysing} onClick={() => cameraRef.current?.click()}><Camera size={15} /> Use camera</button>
            </div>
            <span className="dropzone__hint">JPEG, PNG or WebP · up to 10 MB · one photograph</span>
            <input ref={inputRef} className="sr-only" type="file" accept="image/jpeg,image/png,image/webp" onChange={onInputChange} aria-label="Choose photograph" disabled={!isSessionValid || isLoading || isUploading || isAnalysing} />
            <input ref={cameraRef} className="sr-only" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={onInputChange} aria-label="Capture photograph" disabled={!isSessionValid || isLoading || isUploading || isAnalysing} />
          </div>

          {selectedImage && (
            <div className="upload-preview">
              <img src={selectedImage.dataUrl} alt={`Preview of ${selectedImage.file.name}`} />
              <div className="upload-preview__details">
                <span>IMAGE PREVIEW · READY TO UPLOAD</span>
                <strong>{selectedImage.file.name}</strong>
                <span>{(selectedImage.file.size / (1024 * 1024)).toFixed(2)} MB · {selectedImage.dimensions[0]} × {selectedImage.dimensions[1]} px</span>
                <div className="upload-preview__actions">
                  <button type="button" className="button button--ghost" disabled={isUploading || isAnalysing} onClick={() => { setSelectedImage(null) }}><X size={14} /> Remove</button>
                  <button type="button" className="button button--quiet" disabled={isUploading || isAnalysing} onClick={() => inputRef.current?.click()}><RotateCcw size={14} /> Retake</button>
                </div>
              </div>
            </div>
          )}

          {!photograph && selectedImage && (
            <div className="structure-selector" style={{ marginTop: 14, padding: 16, background: '#f5faf8', borderRadius: 8 }}>
              <span style={{ display: 'block', fontSize: 11, color: '#718087', marginBottom: 8 }}>Structure type</span>
              <div style={{ display: 'flex', gap: 10 }}>
                {structureTypes.map(({ value, label }) => (
                  <button
                    key={value}
                    type="button"
                    className={`structure-button${structureType === value ? ' is-active' : ''}`}
                    onClick={() => setStructureType(value)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {isUploading && (
            <div className="analysis-stages" aria-live="polite">
              <strong style={{ color: '#52676c', fontSize: 11 }}>Uploading photograph…</strong>
            </div>
          )}

          {isAnalysing && (
            <div className="analysis-stages" aria-live="polite">
              <strong style={{ color: '#52676c', fontSize: 11 }}>Running crack detection…</strong>
            </div>
          )}

          {!photograph && selectedImage && (
            <div className="upload-actions" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginTop: 16 }}>
              <span className="guest-results__limit">Analyses remaining: <strong>{analysesRemaining} of 3</strong></span>
              <button type="button" className="button button--primary" disabled={isUploading || isAnalysing || sessionExpired || analysesRemaining < 1 || !isSessionValid || isLoading} onClick={handleUpload}>
                {isUploading ? 'Uploading…' : 'Upload photograph'} <ArrowRight size={15} />
              </button>
            </div>
          )}

          {photograph && !analysis && (
            <div className="upload-actions" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginTop: 16 }}>
              <span className="guest-results__limit">Analyses remaining: <strong>{analysesRemaining} of 3</strong></span>
              <button type="button" className="button button--primary" disabled={isAnalysing || sessionExpired || analysesRemaining < 1 || !isSessionValid || isLoading} onClick={handleAnalyse}>
                {isAnalysing ? 'Analysing…' : 'Run crack analysis'} <ArrowRight size={15} />
              </button>
            </div>
          )}
        </section>

        <div className="upload-main__disclaimer">
          <SafetyNotice />
          <div className="card card--padded" style={{ marginTop: 12 }}>
            <div className="card-heading"><div><h2>Want to see the result view now?</h2><p>Open the bundled sample photograph and its matching model outputs.</p></div></div>
            <button type="button" className="button button--secondary" disabled={isUploading || isAnalysing || sessionExpired || analysesRemaining < 1 || !isSessionValid || isLoading} onClick={() => navigate('/try/results')}>
              View sample analysis <ArrowRight size={14} />
            </button>
          </div>
        </div>
        <p className="form-field__hint" style={{ marginTop: 13, textAlign: 'center' }}>
          {usedAnalyses} of 3 guest analyses used in this session.
        </p>
        <details className="prototype-state-controls">
          <summary>Prototype state controls</summary>
          <p>Preview common support states; these controls do not change backend data.</p>
          <div>
            <button className="button button--secondary" onClick={() => { setSessionExpired((expired) => !expired) }}>
              {sessionExpired ? 'Restore guest session' : 'Show expired session'}
            </button>
            <button className="button button--secondary" onClick={clearSession}>
              Reset guest session
            </button>
          </div>
        </details>
      </main>
    </div>
  )
}
