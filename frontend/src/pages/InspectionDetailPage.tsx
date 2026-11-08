import { ArrowLeft, FileText, ImagePlus, Download } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, type Inspection, type StructureType } from '../types'
import { apiClient } from '../services/api'
import { useAuth } from '../hooks/useAuth'
import { DemoNotice, PageHeading, SafetyNotice, StatusPill } from '../components/Ui'
import { ErrorState } from '../components/ErrorState'
import { LoadingState } from '../components/LoadingState'
import { structureTypes } from '../data/mockData'
import type { PhotographMetadataResponse } from '../types'

const STRUCTURE_LABELS: Record<StructureType, string> = {
  wall: 'Wall',
  beam: 'Beam',
  column: 'Column',
}

export function InspectionDetailPage() {
  const { inspectionId = '' } = useParams()
  const { isAuthenticated, isLoading, getToken } = useAuth()
  const [inspection, setInspection] = useState<Inspection | null>(null)
  const [photographs, setPhotographs] = useState<PhotographMetadataResponse[]>([])
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [notice, setNotice] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [structureType, setStructureType] = useState<StructureType>('wall')
  const previewUrlRef = useRef<string | null>(null)
  const [downloadingPhotoId, setDownloadingPhotoId] = useState<string | null>(null)
  const [generatingReport, setGeneratingReport] = useState(false)
  const [reportError, setReportError] = useState('')
  const [reportNotice, setReportNotice] = useState('')
  const [generatedReportId, setGeneratedReportId] = useState<string | null>(null)
  const [downloadingReport, setDownloadingReport] = useState(false)

  // Attach the Clerk bearer token to the API client once auth resolves.
  useEffect(() => {
    ;(async () => {
      const token = await getToken()
      apiClient.setToken(token ?? null)
    })()
  }, [getToken])

  useEffect(() => {
    return () => {
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current)
      }
    }
  }, [])

  const loadInspection = useCallback(async () => {
    if (!inspectionId) return
    setError('')
    try {
      const [insp] = await Promise.all([
        apiClient.getInspection(inspectionId),
        apiClient.listInspectionPhotographs(inspectionId).then((resp) => {
          setPhotographs(resp.photographs)
        }),
      ])
      setInspection(insp)
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'Failed to load inspection.',
      )
    }
  }, [inspectionId])

  useEffect(() => {
    if (!isLoading && inspectionId) {
      loadInspection()
    }
  }, [inspectionId, isLoading, loadInspection])

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null
    setSelectedFile(file)
    setUploadError('')
    if (file) {
      const url = URL.createObjectURL(file)
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current)
      }
      previewUrlRef.current = url
      setPreviewUrl(url)
    } else {
      setPreviewUrl(null)
    }
  }

  const handleUpload = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!selectedFile || !inspectionId) return
    setUploading(true)
    setUploadError('')
    try {
      await apiClient.uploadPhotograph(inspectionId, selectedFile, structureType)
      setNotice('Photograph uploaded successfully.')
      setSelectedFile(null)
      setPreviewUrl(null)
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current)
        previewUrlRef.current = null
      }
      setStructureType('wall')
      await loadInspection()
    } catch (err) {
      setUploadError(
        err instanceof ApiError ? err.message : 'Upload failed. Please try again.',
      )
    } finally {
      setUploading(false)
    }
  }

  const handleDownload = async (photoId: string) => {
    setDownloadingPhotoId(photoId)
    try {
      const blobUrl = await apiClient.downloadPhotographImage(photoId, 'original')
      const anchor = document.createElement('a')
      anchor.href = blobUrl
      anchor.download = `${photoId}.jpg`
      document.body.appendChild(anchor)
      anchor.click()
      document.body.removeChild(anchor)
      URL.revokeObjectURL(blobUrl)
    } catch (err) {
      setUploadError(
        err instanceof ApiError ? err.message : 'Download failed. Please try again.',
      )
    } finally {
      setDownloadingPhotoId(null)
    }
  }

  const isDraft = inspection?.status === 'draft'
  const canUpload = isAuthenticated && isDraft && !!inspectionId

  const handleGenerateReport = async () => {
    // Prevent duplicate generation requests (each call creates a new
    // backend report) and allow retry after a failure.
    if (generatingReport || !isAuthenticated || !inspectionId) return
    setGeneratingReport(true)
    setReportError('')
    try {
      const report = await apiClient.generateReport(inspectionId)
      setGeneratedReportId(report.report_id)
      setReportNotice(
        `Report generated successfully (ID: ${report.report_id}). Download it below.`,
      )
    } catch (err) {
      setGeneratedReportId(null)
      setReportNotice('')
      setReportError(
        err instanceof ApiError ? err.message : 'Report generation failed. Please try again.',
      )
    } finally {
      setGeneratingReport(false)
    }
  }

  const handleDownloadReport = async () => {
    if (downloadingReport || !generatedReportId) return
    setDownloadingReport(true)
    setReportError('')
    try {
      const blobUrl = await apiClient.downloadReportPdf(generatedReportId)
      const anchor = document.createElement('a')
      anchor.href = blobUrl
      // Matches the backend's Content-Disposition attachment filename.
      anchor.download = `cracksight-report-${generatedReportId}.pdf`
      document.body.appendChild(anchor)
      anchor.click()
      document.body.removeChild(anchor)
      URL.revokeObjectURL(blobUrl)
    } catch (err) {
      setReportError(
        err instanceof ApiError ? err.message : 'Report download failed. Please try again.',
      )
    } finally {
      setDownloadingReport(false)
    }
  }

  if (isLoading) {
    return (
      <div className="app-content" style={{ padding: 40, display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center' }}>
        <LoadingState message="Resolving session…" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="app-content" style={{ padding: 40, display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center' }}>
        <ErrorState
          title="Unable to load inspection"
          message={error}
          retryable
          onRetry={loadInspection}
        />
      </div>
    )
  }

  if (!inspection) {
    return (
      <div className="app-content" style={{ padding: 40, display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center' }}>
        <LoadingState message="Loading inspection…" />
      </div>
    )
  }

  return (
    <>
      <Link to="/app/history" className="upload-back">
        <ArrowLeft size={14} /> Back to inspections
      </Link>
      <PageHeading
        eyebrow={`Inspection ${inspection.id}`}
        title={inspection.title}
        action={
          <>
            <span className="status-badge">
              <StatusPill status={inspection.status === 'completed' ? 'Completed' : 'Draft'} />
            </span>
          </>
        }
      />
      {(notice || uploadError) && (
        <div style={{ margin: '0 16px 16px 16px' }}>
          {notice && <DemoNotice>{notice}</DemoNotice>}
          {uploadError && <p className="prototype-alert" role="alert">{uploadError}</p>}
        </div>
      )}
      <SafetyNotice compact />

      <section className="card card--padded" style={{ margin: '16px' }}>
        <div className="card-heading">
          <div>
            <h2>Photographs</h2>
            <p>
              {photographs.length} {photographs.length === 1 ? 'photo' : 'photos'} &middot;
              {inspection.photograph_count} total
            </p>
          </div>
        </div>

        {photographs.length === 0 && (
          <div className="empty-state" style={{ minHeight: 180 }}>
            <span className="empty-state__icon">
              <ImagePlus size={20} />
            </span>
            <h3 className="empty-state__title">No photographs added</h3>
            <p className="empty-state__description">
              Upload a photograph to begin building this inspection. Each photo is assigned a
              structure type (wall, beam or column) and stored privately.
            </p>
            {canUpload && (
              <div style={{ marginTop: 17 }}>
                <p className="empty-state__description" style={{ color: '#1d2b33', fontSize: 12, fontWeight: 600 }}>
                  Use the upload form below to add a photograph.
                </p>
              </div>
            )}
          </div>
        )}

        {photographs.length > 0 && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 14, marginTop: 10 }}>
            {photographs.map((photo) => (
              <div
                key={photo.id}
                className="photo-card"
                style={{
                  border: '1px solid #e6ebe9',
                  borderRadius: 10,
                  padding: 12,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 8,
                  background: '#fbfcfc',
                }}
              >
                <div style={{ fontSize: 11, color: '#718087', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Structure type
                </div>
                <div style={{ fontSize: 15, fontWeight: 600, color: '#1d2b33' }}>
                  {STRUCTURE_LABELS[photo.structure_type]}
                </div>
                <div style={{ fontSize: 11, color: '#718087' }}>
                  {new Date(photo.created_at).toLocaleDateString()}
                </div>
                <button
                  type="button"
                  onClick={() => handleDownload(photo.id)}
                  disabled={downloadingPhotoId === photo.id}
                  className="button button--ghost"
                  style={{ fontSize: 11, padding: '6px 10px', marginTop: 6 }}
                >
                  {downloadingPhotoId === photo.id ? (
                    'Preparing…'
                  ) : (
                    <span>
                      <Download size={13} /> Download original
                    </span>
                  )}
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {isAuthenticated && (
        <section className="card card--padded" style={{ margin: '16px' }}>
          <div className="card-heading">
            <div>
              <h2>PDF report</h2>
              <p>
                Generate a branded PDF inspection report with all photographs and analysis
                results. Available for Draft and Completed inspections.
              </p>
            </div>
          </div>
          {reportNotice && <p className="form-field__hint" role="status">{reportNotice}</p>}
          {reportError && <p className="prototype-alert" role="alert">{reportError}</p>}
          <div className="form-footer" style={{ marginTop: 12 }}>
            <button
              type="button"
              className="button button--secondary"
              onClick={handleGenerateReport}
              disabled={generatingReport}
            >
              {generatingReport ? (
                'Generating…'
              ) : (
                <span>
                  <FileText size={14} /> Generate report
                </span>
              )}
            </button>
            {generatedReportId && (
              <button
                type="button"
                className="button button--primary"
                onClick={handleDownloadReport}
                disabled={downloadingReport}
              >
                {downloadingReport ? (
                  'Preparing…'
                ) : (
                  <span>
                    <Download size={14} /> Download PDF report
                  </span>
                )}
              </button>
            )}
          </div>
        </section>
      )}

      {canUpload && (
        <section className="card card--padded" style={{ margin: '16px' }}>
          <div className="card-heading">
            <div>
              <h2>Add photograph</h2>
              <p>Select an image and assign its structure type before uploading.</p>
            </div>
          </div>
          <form className="create-form" onSubmit={handleUpload} noValidate style={{ marginTop: 12 }}>
            <div className="form-field">
              <label htmlFor="upload-file">Photograph <span>Required</span></label>
              <input
                id="upload-file"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={handleFileChange}
              />
              <span className="form-field__hint">JPEG, PNG or WebP. The image content is validated on the server.</span>
            </div>
            {previewUrl && (
              <div style={{ marginTop: 10, border: '1px solid #e6ebe9', borderRadius: 8, padding: 10, background: '#fbfcfc', display: 'flex', alignItems: 'center', gap: 10, maxWidth: 320 }}>
                <img src={previewUrl} alt="Preview" style={{ width: 72, height: 72, objectFit: 'cover', borderRadius: 6 }} />
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#1d2b33' }}>{selectedFile?.name}</div>
                  <div style={{ fontSize: 11, color: '#718087' }}>{((selectedFile?.size ?? 0) / 1024).toFixed(1)} KB</div>
                </div>
              </div>
            )}
            <div className="form-field" style={{ marginTop: 14 }}>
              <label htmlFor="upload-structure">Structure type</label>
              <select
                id="upload-structure"
                value={structureType}
                onChange={(event) => setStructureType(event.target.value as StructureType)}
              >
                {structureTypes.map((type) => (
                  <option key={type} value={type.toLowerCase() as StructureType}>
                    {type}
                  </option>
                ))}
              </select>
            </div>
            {uploadError && <p className="prototype-alert" role="alert">{uploadError}</p>}
            <div className="form-footer" style={{ marginTop: 16 }}>
              <button
                type="button"
                className="button button--secondary"
                onClick={() => {
                  setSelectedFile(null)
                  setPreviewUrl(null)
                  if (previewUrlRef.current) {
                    URL.revokeObjectURL(previewUrlRef.current)
                    previewUrlRef.current = null
                  }
                  setUploadError('')
                }}
                disabled={uploading}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="button button--primary"
                disabled={uploading || !selectedFile}
              >
                {uploading ? 'Uploading…' : 'Upload photograph'}
              </button>
            </div>
          </form>
        </section>
      )}

      {!isAuthenticated && (
        <DemoNotice>
          Please sign in to add photographs to this inspection.
        </DemoNotice>
      )}
      {isAuthenticated && inspection && !isDraft && (
        <DemoNotice>
          Completed inspections are read-only. Reopen the inspection to add photographs.
        </DemoNotice>
      )}
    </>
  )
}
