import {
  ArrowLeft,
  Check,
  Download,
  FileText,
  ImagePlus,
  MapPin,
  RotateCcw,
} from 'lucide-react'
import { useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { ResultViewer } from '../components/ResultViewer'
import { DemoNotice, PageHeading, SafetyNotice, StatusPill } from '../components/Ui'
import { useAuth } from '../hooks/useAuth'
import { initialInspections, type VerificationStatus } from '../data/mockData'

export function InspectionDetailPage() {
  const { inspectionId = '' } = useParams()
  const { isAuthenticated, isLoading } = useAuth()
  const inspections = initialInspections
  const inspection = inspections.find((item) => item.id === inspectionId)
  const [verification, setVerification] = useState<VerificationStatus>(inspection?.verification ?? 'Not verified')
  const [notice, setNotice] = useState('')
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="empty-state card" style={{ padding: 40 }}>
        <div style={{ width: 40, height: 40, border: '3px solid #e6ebe9', borderTopColor: '#167f78', borderRadius: '50%', animation: 'spin 0.8s linear infinite', margin: '0 auto 16px' }} />
        <h3>Resolving session…</h3>
        <p>Please wait while your authentication state is checked.</p>
      </div>
    )
  }

  if (!inspection) {
    return (
      <div className="empty-state card">
        <h3>Inspection not found</h3><p>This sample record may no longer be available in the prototype session.</p>
        <Link className="button button--secondary" to="/app/history">Back to history</Link>
      </div>
    )
  }

  const isDraft = inspection.status === 'Draft'
  const hasPhotograph = inspection.photoCount > 0
  const stateNotice = (location.state as { prototypeNotice?: string } | null)?.prototypeNotice

  return (
    <>
      <Link to="/app/history" className="upload-back"><ArrowLeft size={14} /> Back to inspections</Link>
      <PageHeading
        eyebrow={`Inspection ${inspection.id}`}
        title={inspection.title}
        description={<span className="inspection-location"><MapPin size={13} /> {inspection.location} · {inspection.buildingType}</span>}
        action={
          <>
            <Link className="button button--secondary" to="/app/reports"><FileText size={15} /> Report preview</Link>
              <button
                className="button button--primary"
                onClick={() => {
                  if (!isAuthenticated) {
                    setNotice('Please sign in to manage inspections.')
                    return
                  }
                  setNotice(isDraft ? 'Marked completed in prototype state. The record is read-only until reopened.' : 'Inspection reopened as a draft in prototype state.')
                }}
              >
              {isDraft ? <Check size={15} /> : <RotateCcw size={15} />}
              {isDraft ? 'Mark as completed' : 'Reopen draft'}
            </button>
          </>
        }
      />
      {(stateNotice || notice) && <DemoNotice>{notice || stateNotice}</DemoNotice>}
      <div style={{ marginTop: 14, marginBottom: 14 }}>
        <DemoNotice>{isLoading ? 'Resolving session…' : 'Sample details and image outputs are illustrative. Editing and lifecycle actions are held in memory only.'}</DemoNotice>
      </div>
      <div className="detail-summary">
        <div className="detail-summary__item"><small>STATUS</small><StatusPill status={inspection.status} /></div>
        <div className="detail-summary__item"><small>COMPONENT</small><strong>{inspection.structure}</strong></div>
        <div className="detail-summary__item"><small>PHOTOGRAPHS</small><strong>{inspection.photoCount} sample {inspection.photoCount === 1 ? 'photo' : 'photos'}</strong></div>
      </div>
      <div className="inspection-detail-grid">
        <section>
          <div className="card card--padded">
            <div className="card-heading">
              <div><h2>Photographs</h2><p>{inspection.photoCount} {inspection.photoCount === 1 ? 'photo' : 'photos'} · {inspection.structure}</p></div>
              {isDraft && <button className="button button--secondary" onClick={() => { setNotice('Photograph upload will be connected to the backend in the next milestone.') }}><ImagePlus size={15} /> Add sample photo</button>}
            </div>
            {hasPhotograph ? (
              <>
                <ResultViewer />
                <div className="result-meta" style={{ marginTop: 17 }}>
                  <div className="result-meta__row"><span>Model version</span><strong>m3_baseline_b1 · ResNet-34 U-Net</strong></div>
                  <div className="result-meta__row"><span>Processed</span><strong>02 Nov 2026 · 10:42</strong></div>
                  <div className="result-meta__row"><span>Image dimensions</span><strong>416 × 416 pixels</strong></div>
                </div>
              </>
            ) : (
              <div className="empty-state">
                <span className="empty-state__icon"><ImagePlus size={20} /></span>
                <h3>No photographs added</h3>
                <p>Add a sample photograph to preview image comparison and analysis details. This action stays in the prototype.</p>
                {isDraft && <button className="button button--primary" onClick={() => setNotice('Photograph upload will be connected to the backend in the next milestone.')}>Add sample photograph</button>}
              </div>
            )}
          </div>
          {hasPhotograph && <section className="card card--padded" style={{ marginTop: 14 }}>
            <div className="card-heading">
              <div><h2>Inspector observation</h2><p>Human-entered note, separate from the AI output</p></div>
              <button className="button button--ghost" disabled={!isDraft} onClick={() => setNotice('Observation editing is represented in the prototype only.')}>Edit note</button>
            </div>
            <p className="text-muted" style={{ fontSize: 11, lineHeight: 1.65 }}>
              {inspection.notes || 'Fine surface crack visible across the wall finish. Verify extent and context during the site review.'}
            </p>
          </section>}
        </section>

        <aside className="guest-results__side">
          {hasPhotograph ? <section className="card card--padded">
            <div className="card-heading"><div><h2>AI prediction review</h2><p>Human verification required</p></div></div>
            <div className="measurement"><small>Predicted crack pixels</small><strong className="measurement__value">2,814 px</strong><small>Image-space measurement only</small></div>
            <div className="form-field" style={{ marginTop: 15 }}>
              <label htmlFor="verification-status">Verification status</label>
              <select
                id="verification-status"
                value={verification}
                disabled={!isDraft}
                onChange={(event) => setVerification(event.target.value as VerificationStatus)}
              >
                <option>Not verified</option><option>Correct detection</option><option>Partially correct</option><option>Incorrect detection</option>
              </select>
              {!isDraft && <span className="form-field__hint">Completed inspections are read-only. Reopen to edit.</span>}
            </div>
          </section> : <section className="card card--padded empty-state"><span className="empty-state__icon"><ImagePlus size={20} /></span><h3>Analysis not available</h3><p>Add a photograph before reviewing an AI prediction or pixel measurements.</p></section>}
          <SafetyNotice />
          {hasPhotograph && <section className="card card--padded">
            <div className="card-heading"><div><h2>Downloads</h2><p>Individual result files</p></div></div>
            <div className="quick-actions">
              <a className="quick-action" href="/demo/crack-wall.jpg" download><span className="quick-action__icon"><Download size={15} /></span><span className="quick-action__text"><strong>Original photograph</strong><small>JPEG · sample asset</small></span></a>
              <a className="quick-action" href="/demo/crack-mask.png" download><span className="quick-action__icon"><Download size={15} /></span><span className="quick-action__text"><strong>Predicted mask</strong><small>PNG · sample output</small></span></a>
            </div>
          </section>}
        </aside>
      </div>
    </>
  )
}
