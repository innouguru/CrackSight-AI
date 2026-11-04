import { ArrowLeft, Download, FileText } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Brand } from '../components/Brand'
import { ResultViewer } from '../components/ResultViewer'
import { DemoNotice, SafetyNotice } from '../components/Ui'
import { useAuth } from '../hooks/useAuth'
import { apiClient } from '../services/api'
import type { AnalysisResponse } from '../types'

interface ResultLocationState {
  photographId?: string
  structureType?: string
  fileName?: string
  imageSize?: [number, number]
}

export function ResultsPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const { isGuest, isLoading } = useAuth()
  const state = (location.state as ResultLocationState | null) ?? null

  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null)
  const [originalUrl, setOriginalUrl] = useState<string | null>(null)
  const [maskUrl, setMaskUrl] = useState<string | null>(null)
  const [overlayUrl, setOverlayUrl] = useState<string | null>(null)
  const [isFetching, setIsFetching] = useState(false)
  const [fetchError, setFetchError] = useState<string | null>(null)

  const photographId = state?.photographId
  const isSample = !photographId

  useEffect(() => {
    if (isSample || isLoading) return

    let cancelled = false

    async function loadResults() {
      setIsFetching(true)
      setFetchError(null)
      try {
        const photoId = photographId!
        // Fetch photograph details to get the analysis response
        const result = await apiClient.getPhotograph(photoId)
        setAnalysis({
          photograph_id: result.id,
          prediction_mask_key: result.prediction_mask_key ?? '',
          prediction_overlay_key: result.prediction_overlay_key ?? '',
          original_image_key: result.original_image_key,
          model_version: result.model_version ?? 'unknown',
          prediction_timestamp: result.prediction_timestamp ?? new Date().toISOString(),
          inference_duration_ms: 0,
          processing_status: 'completed',
          original_image_size: [0, 0],
          pixel_measurements: result.pixel_measurements as import('../types').PixelMeasurements | null,
          analyses_remaining: null,
        })

        // Download result files as blob URLs for display
        const [orig, mask, overlay] = await Promise.allSettled([
          apiClient.downloadGuestResult(photoId, 'original'),
          apiClient.downloadGuestResult(photoId, 'mask'),
          apiClient.downloadGuestResult(photoId, 'overlay'),
        ])

        if (!cancelled) {
          if (orig.status === 'fulfilled') setOriginalUrl(orig.value)
          if (mask.status === 'fulfilled') setMaskUrl(mask.value)
          if (overlay.status === 'fulfilled') setOverlayUrl(overlay.value)
        }
      } catch (err) {
        if (!cancelled) {
          setFetchError(err instanceof Error ? err.message : 'Failed to load results.')
        }
      } finally {
        if (!cancelled) setIsFetching(false)
      }
    }

    void loadResults()

    return () => {
      cancelled = true
      if (originalUrl) URL.revokeObjectURL(originalUrl)
      if (maskUrl) URL.revokeObjectURL(maskUrl)
      if (overlayUrl) URL.revokeObjectURL(overlayUrl)
    }
  }, [photographId, isSample, isLoading, originalUrl, maskUrl, overlayUrl])

  const analysesRemaining = isGuest ? null : null

  const crackPixels = analysis?.pixel_measurements?.crack_pixel_count ?? null
  const crackPercentage = analysis?.pixel_measurements?.crack_pixel_percentage ?? null

  return (
    <div className="upload-page">
      <header className="upload-header">
        <Link to="/"><Brand /></Link>
        <div className="upload-header__right"><span>Guest session · {analysesRemaining ?? 0} analyses remaining</span><Link className="button button--secondary" to="/sign-in">Sign in</Link></div>
      </header>
      <main className="guest-results">
        <Link className="upload-back" to="/try"><ArrowLeft size={14} /> Back to guest analysis</Link>
        <div className="guest-results__header">
          <div>
            <p className="eyebrow">{isSample ? 'Sample result · wall' : 'Guest analysis result'}</p>
            <h1>Crack analysis review</h1>
            <p className="page-heading__description">Compare the original photograph with the predicted mask and overlay.</p>
          </div>
          <span className="guest-results__limit">Guest session · <strong>{analysesRemaining ?? 0} analyses left</strong></span>
        </div>
        {isLoading && <p className="prototype-alert" role="status">Resolving session…</p>}
        {isFetching && <p className="prototype-alert" role="status">Loading results…</p>}
        {fetchError && <p className="prototype-alert" role="alert">{fetchError}</p>}
        {isSample && (
          <div style={{ marginBottom: 13 }}>
            <DemoNotice>
              This result is an included model sample. It is not a new inference request and is not connected to the backend.
            </DemoNotice>
          </div>
        )}
        {!isSample && (
          <div style={{ marginBottom: 13 }}>
            <DemoNotice>
              Results are generated by the trained crack segmentation model via the backend. AI predictions require human review and do not assess structural safety.
            </DemoNotice>
          </div>
        )}
        <div className="guest-results__grid">
          <section className="card card--padded">
            <div className="card-heading"><div><h2>Photograph comparison</h2><p>{isSample ? 'Sample wall photograph · baseline model output' : 'Your uploaded photograph · real model output'}</p></div></div>
            <ResultViewer
              originalImage={originalUrl ?? (isSample ? '/demo/crack-wall.jpg' : '')}
              maskImage={maskUrl ?? (isSample ? '/demo/crack-mask.png' : '')}
              overlayImage={overlayUrl ?? (isSample ? '/demo/crack-overlay.png' : '')}
              uploadedImage={!isSample}
              dimensions={state?.imageSize}
            />
          </section>
          <aside className="guest-results__side">
            <section className="card card--padded">
              <div className="card-heading"><div><h2>Prediction details</h2><p>Model output · requires human review</p></div></div>
              {crackPixels !== null && (
                <div className="measurement">
                  <small>Predicted crack pixels</small>
                  <strong className="measurement__value">{crackPixels.toLocaleString()} px</strong>
                  <small>Image-space measurement only</small>
                </div>
              )}
              {crackPercentage !== null && (
                <div className="measurement" style={{ marginTop: 8 }}>
                  <small>Crack area</small>
                  <strong className="measurement__value">{crackPercentage}%</strong>
                  <small>of image pixels</small>
                </div>
              )}
              <div className="result-meta" style={{ marginTop: 15 }}>
                {!isSample && <div className="result-meta__row"><span>Structure type</span><strong>{state?.structureType ?? 'Wall'}</strong></div>}
                <div className="result-meta__row"><span>Model version</span><strong>{analysis?.model_version ?? 'm3_baseline_b1'}</strong></div>
                <div className="result-meta__row">
                  <span>{isSample ? 'Image dimensions' : 'Original image dimensions'}</span>
                  <strong>
                    {state?.imageSize ? `${state.imageSize[0]} × ${state.imageSize[1]} px` : '416 × 416 px'}
                  </strong>
                </div>
                <div className="result-meta__row"><span>Processing time</span><strong>{analysis ? `${analysis.inference_duration_ms} ms` : '1.8 sec · sample'}</strong></div>
                {analysis?.pixel_measurements?.bounding_box && (
                  <div className="result-meta__row">
                    <span>Crack bounding box</span>
                    <strong>
                      {analysis.pixel_measurements.bounding_box.min_x} × {analysis.pixel_measurements.bounding_box.min_y} to {analysis.pixel_measurements.bounding_box.max_x} × {analysis.pixel_measurements.bounding_box.max_y} px
                    </strong>
                  </div>
                )}
              </div>
            </section>
            <SafetyNotice />
            <section className="guest-results__cta">
              <h3>Keep your inspections together</h3>
              <p>Create an account to explore the registered-user dashboard and inspection history.</p>
              <Link className="button button--primary" to="/sign-up">Create an account <FileText size={14} /></Link>
            </section>
            <div className="card card--padded">
              <div className="card-heading"><div><h2>Download result files</h2><p>{isSample ? 'Prototype assets only' : 'Download individual result files'}</p></div></div>
              <div className="quick-actions">
                {originalUrl && (
                  <a className="quick-action" href={originalUrl} download={state?.fileName ?? 'crack-wall.jpg'}><span className="quick-action__icon"><Download size={15} /></span><span className="quick-action__text"><strong>Original photograph</strong><small>{isSample ? 'JPEG · sample' : 'JPEG · uploaded'}</small></span></a>
                )}
                {maskUrl && (
                  <a className="quick-action" href={maskUrl} download><span className="quick-action__icon"><Download size={15} /></span><span className="quick-action__text"><strong>Predicted mask</strong><small>PNG</small></span></a>
                )}
                {overlayUrl && (
                  <a className="quick-action" href={overlayUrl} download><span className="quick-action__icon"><Download size={15} /></span><span className="quick-action__text"><strong>Overlay</strong><small>PNG</small></span></a>
                )}
              </div>
            </div>
          </aside>
        </div>
        <button className="button button--secondary" style={{ marginTop: 16 }} onClick={() => navigate('/try')}>
          <ArrowLeft size={14} /> Try another sample
        </button>
      </main>
    </div>
  )
}
