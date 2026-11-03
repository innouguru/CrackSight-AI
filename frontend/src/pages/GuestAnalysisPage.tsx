import { ArrowLeft, ArrowRight, Camera, Check, CloudUpload, FileImage, RotateCcw, X } from 'lucide-react'
import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Brand } from '../components/Brand'
import { DemoNotice, SafetyNotice } from '../components/Ui'
import { useGuestSession } from '../hooks/useGuestSession'

const stages = [
  'Uploading photograph',
  'Preparing image',
  'Running crack detection',
  'Generating results',
]

interface SelectedImage {
  name: string
  size: number
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
  const { validation, isLoading, error: sessionError, createSession, clearSession } = useGuestSession()
  const [selectedImage, setSelectedImage] = useState<SelectedImage | null>(null)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const [activeStage, setActiveStage] = useState(-1)
  const [busy, setBusy] = useState(false)
  const [sessionExpired, setSessionExpired] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const cameraRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  const analysesRemaining = validation?.analyses_remaining ?? 0
  const isSessionValid = validation?.valid ?? false

  useEffect(() => {
    void createSession()
  }, [createSession])

  async function chooseFile(file?: File) {
    setError('')
    if (!file) return
    const validTypes = ['image/jpeg', 'image/png', 'image/webp']
    if (!validTypes.includes(file.type)) {
      setSelectedImage(null)
      setError('Choose a JPEG, PNG or WebP image.')
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      setSelectedImage(null)
      setError('This image is larger than the 10 MB prototype limit. Choose a smaller file.')
      return
    }
    try {
      const dataUrl = await readImage(file)
      const dimensions = await getImageDimensions(dataUrl)
      setSelectedImage({ name: file.name, size: file.size, dataUrl, dimensions })
    } catch (readError) {
      setSelectedImage(null)
      setError(readError instanceof Error ? readError.message : 'Could not preview this image.')
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

  async function runAnalysis(useSample = false) {
    if (busy) return
    if (!isSessionValid) {
      setError('Guest session is not available. Please refresh to start a new session.')
      return
    }
    if (sessionExpired) {
      setError('This guest session has expired. Start a new session to continue.')
      return
    }
    if (analysesRemaining < 1) {
      setError('This guest session has no analyses remaining. Create an account to explore the registered-user screens.')
      return
    }
    setBusy(true)
    setError('')
    for (let index = 0; index < stages.length; index += 1) {
      setActiveStage(index)
      await new Promise((resolve) => window.setTimeout(resolve, 420))
    }
    setBusy(false)
    navigate('/try/results', {
      state: useSample || !selectedImage
        ? null
        : {
            imageDataUrl: selectedImage.dataUrl,
            fileName: selectedImage.name,
            imageSize: selectedImage.dimensions,
          },
    })
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
              <span>Guest session · {isSessionValid ? 'active' : 'expired'} · {analysesRemaining} analyses remaining</span>
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
          <p>Upload an image to explore the analysis flow, or open the included sample result.</p>
        </div>

        {isLoading && <p className="prototype-alert" role="status">Establishing your guest session…</p>}
        {sessionError && <p className="prototype-alert" role="alert">{sessionError}</p>}
        {sessionExpired && <p className="prototype-alert" role="alert">This guest session has expired. Its results are unavailable after 24 hours.</p>}
        {analysesRemaining < 1 && !sessionExpired && !isLoading && (
          <p className="prototype-alert" role="status">No guest analyses remain in this session. Create an account to explore the registered-user screens.</p>
        )}
        <DemoNotice>
          This is a visual prototype foundation. Guest session creation is connected to the backend. Upload and analysis will be connected to the backend in the next milestone.
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
              <button type="button" className="button button--secondary" disabled={!isSessionValid || isLoading || busy} onClick={() => inputRef.current?.click()}><FileImage size={15} /> Choose image</button>
              <button type="button" className="button button--secondary" disabled={!isSessionValid || isLoading || busy} onClick={() => cameraRef.current?.click()}><Camera size={15} /> Use camera</button>
            </div>
            <span className="dropzone__hint">JPEG, PNG or WebP · up to 10 MB · one photograph</span>
            <input ref={inputRef} className="sr-only" type="file" accept="image/jpeg,image/png,image/webp" onChange={onInputChange} aria-label="Choose photograph" disabled={!isSessionValid || isLoading || busy} />
            <input ref={cameraRef} className="sr-only" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={onInputChange} aria-label="Capture photograph" disabled={!isSessionValid || isLoading || busy} />
          </div>

          {selectedImage && (
            <div className="upload-preview">
              <img src={selectedImage.dataUrl} alt={`Preview of ${selectedImage.name}`} />
              <div className="upload-preview__details">
                <span>IMAGE PREVIEW · NOT UPLOADED</span>
                <strong>{selectedImage.name}</strong>
                <span>{(selectedImage.size / (1024 * 1024)).toFixed(2)} MB · Ready to preview</span>
                <div className="upload-preview__actions">
                  <button type="button" className="button button--ghost" disabled={busy} onClick={() => { setSelectedImage(null); setActiveStage(-1) }}><X size={14} /> Remove</button>
                  <button type="button" className="button button--quiet" disabled={busy} onClick={() => inputRef.current?.click()}><RotateCcw size={14} /> Retake</button>
                </div>
              </div>
            </div>
          )}

          {busy && (
            <div className="analysis-stages" aria-live="polite">
              <strong style={{ color: '#52676c', fontSize: 11 }}>Sample workflow stages</strong>
              {stages.map((stage, index) => (
                <div className={`analysis-stage${index === activeStage ? ' is-current' : ''}${index < activeStage ? ' is-done' : ''}`} key={stage}>
                  <span className="analysis-stage__mark">{index < activeStage ? <Check size={12} /> : index + 1}</span>{stage}
                </div>
              ))}
            </div>
          )}

          {error && <p className="prototype-alert" role="alert">{error}</p>}
          <div className="upload-actions" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginTop: 16 }}>
            <span className="guest-results__limit">Analyses remaining: <strong>{analysesRemaining} of 3</strong></span>
            <button type="button" className="button button--primary" disabled={busy || sessionExpired || analysesRemaining < 1 || !selectedImage || !isSessionValid || isLoading} onClick={() => void runAnalysis(false)}>
              {busy ? 'Preparing sample…' : selectedImage ? 'Preview sample result' : 'Select a photo to preview'}
              {busy ? null : <ArrowRight size={15} />}
            </button>
          </div>
        </section>

        <div className="upload-main__disclaimer">
          <SafetyNotice />
          <div className="card card--padded" style={{ marginTop: 12 }}>
            <div className="card-heading"><div><h2>Want to see the result view now?</h2><p>Open the bundled sample photograph and its matching model outputs.</p></div></div>
            <button type="button" className="button button--secondary" disabled={busy || sessionExpired || analysesRemaining < 1 || !isSessionValid || isLoading} onClick={() => void runAnalysis(true)}>
              {busy ? 'Preparing sample…' : 'Open sample analysis'} <ArrowRight size={14} />
            </button>
          </div>
        </div>
        <p className="form-field__hint" style={{ marginTop: 13, textAlign: 'center' }}>
          {usedAnalyses} of 3 guest analyses used in this prototype session.
        </p>
        <details className="prototype-state-controls">
          <summary>Prototype state controls</summary>
          <p>Preview common support states; these controls do not change backend data.</p>
          <div>
            <button className="button button--secondary" onClick={() => { setSessionExpired((expired) => !expired); setError('') }}>
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
