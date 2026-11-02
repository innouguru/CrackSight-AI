import { ArrowLeft, Download, FileText } from 'lucide-react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Brand } from '../components/Brand'
import { ResultViewer } from '../components/ResultViewer'
import { DemoNotice, SafetyNotice } from '../components/Ui'
import { usePrototype } from '../data/usePrototype'
import { demoImages } from '../data/mockData'

interface ResultLocationState {
  imageDataUrl?: string
  fileName?: string
  imageSize?: [number, number]
}

export function ResultsPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const { guestAnalysesRemaining } = usePrototype()
  const state = (location.state as ResultLocationState | null) ?? null
  const uploaded = Boolean(state?.imageDataUrl)

  return (
    <div className="upload-page">
      <header className="upload-header">
        <Link to="/"><Brand /></Link>
        <div className="upload-header__right"><span>Guest session · {guestAnalysesRemaining} analyses remaining</span><Link className="button button--secondary" to="/sign-in">Sign in</Link></div>
      </header>
      <main className="guest-results">
        <Link className="upload-back" to="/try"><ArrowLeft size={14} /> Back to guest analysis</Link>
        <div className="guest-results__header">
          <div><p className="eyebrow">Sample result · wall</p><h1>Crack analysis review</h1><p className="page-heading__description">Compare the original photograph with the predicted mask and overlay.</p></div>
          <span className="guest-results__limit">Guest session · <strong>{guestAnalysesRemaining} analyses left</strong></span>
        </div>
        {uploaded && (
          <div style={{ marginBottom: 13 }}>
            <DemoNotice>
              “{state?.fileName}” is shown as your browser-only upload preview. The mask and overlay below are bundled sample outputs and were not generated from this photograph.
            </DemoNotice>
          </div>
        )}
        {!uploaded && (
          <div style={{ marginBottom: 13 }}>
            <DemoNotice>
              This result is an included model sample. It is not a new inference request and is not connected to the backend.
            </DemoNotice>
          </div>
        )}
        <div className="guest-results__grid">
          <section className="card card--padded">
            <div className="card-heading"><div><h2>Photograph comparison</h2><p>{uploaded ? 'Your uploaded image preview and illustrative sample output' : 'Sample wall photograph · baseline model output'}</p></div></div>
            <ResultViewer
              originalImage={state?.imageDataUrl ?? demoImages.original}
              uploadedImage={uploaded}
              dimensions={state?.imageSize}
            />
          </section>
          <aside className="guest-results__side">
            <section className="card card--padded">
              <div className="card-heading"><div><h2>Prediction details</h2><p>Model output · requires human review</p></div></div>
              <div className="measurement">
                <small>{uploaded ? 'Sample predicted crack pixels' : 'Predicted crack pixels'}</small>
                <strong className="measurement__value">2,814 px</strong>
                <small>{uploaded ? 'Illustrative sample measurement only' : 'Image-space measurement only'}</small>
              </div>
              <div className="result-meta" style={{ marginTop: 15 }}>
                <div className="result-meta__row"><span>Structure type</span><strong>Wall</strong></div>
                <div className="result-meta__row"><span>Model version</span><strong>m3_baseline_b1</strong></div>
                <div className="result-meta__row">
                  <span>{uploaded ? 'Uploaded image dimensions' : 'Image dimensions'}</span>
                  <strong>{uploaded && state?.imageSize ? `${state.imageSize[0]} × ${state.imageSize[1]} px` : '416 × 416 px'}</strong>
                </div>
                {uploaded && <div className="result-meta__row"><span>Sample output dimensions</span><strong>416 × 416 px</strong></div>}
                <div className="result-meta__row"><span>Processing time</span><strong>1.8 sec · sample</strong></div>
              </div>
            </section>
            <SafetyNotice />
            <section className="guest-results__cta">
              <h3>Keep your inspections together</h3>
              <p>Create an account to explore the registered-user dashboard and inspection history.</p>
              <Link className="button button--primary" to="/sign-up">Create an account <FileText size={14} /></Link>
            </section>
            <div className="card card--padded">
              <div className="card-heading"><div><h2>Download result files</h2><p>{uploaded ? 'Original preview plus sample outputs' : 'Prototype assets only'}</p></div></div>
              <div className="quick-actions">
                  <a className="quick-action" href={state?.imageDataUrl ?? demoImages.original} download={state?.fileName ?? 'crack-wall.jpg'}><span className="quick-action__icon"><Download size={15} /></span><span className="quick-action__text"><strong>{uploaded ? 'Your preview image' : 'Original photo'}</strong><small>{uploaded ? 'Browser-only upload' : 'JPEG · sample'}</small></span></a>
                <a className="quick-action" href={demoImages.mask} download><span className="quick-action__icon"><Download size={15} /></span><span className="quick-action__text"><strong>Predicted mask</strong><small>PNG</small></span></a>
                <a className="quick-action" href={demoImages.overlay} download><span className="quick-action__icon"><Download size={15} /></span><span className="quick-action__text"><strong>Overlay</strong><small>PNG</small></span></a>
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
