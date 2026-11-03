import { ArrowLeft, ArrowRight, ClipboardPlus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { DemoNotice, PageHeading, SafetyNotice } from '../components/Ui'
import { useAuth } from '../hooks/useAuth'
import { structureTypes } from '../data/mockData'

export function NewInspectionPage() {
  const { isAuthenticated, isLoading } = useAuth()
  const [title, setTitle] = useState('')
  const [location, setLocation] = useState('')
  const [buildingType, setBuildingType] = useState('')
  const [structure, setStructure] = useState('Wall')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')
  const [inspectionDate] = useState(() =>
    new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium' }).format(new Date()),
  )

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!title.trim()) {
      setError('Add an inspection title to continue.')
      return
    }
    if (structure !== 'Wall' && structure !== 'Beam' && structure !== 'Column') {
      setError('Choose a supported structure type.')
      return
    }
    if (!isAuthenticated) {
      setError('Please sign in to create and save inspections.')
      return
    }
    setError('')
  }

  return (
    <>
      <Link to="/app/history" className="upload-back"><ArrowLeft size={14} /> Back to inspections</Link>
      <PageHeading
        eyebrow="Inspection setup"
        title="New inspection"
        description="Add the basics now. You can attach photographs and observations as the inspection progresses."
      />
      <DemoNotice>
        {isLoading ? 'Resolving your session…' : !isAuthenticated ? 'Please sign in to create and save inspections. Inspection creation will be connected to your account in the next milestone.' : 'Creating an inspection here updates only the current browser session. No record is sent to the backend.'}
      </DemoNotice>
      <div className="create-layout" style={{ marginTop: 15 }}>
        <form className="card card--padded create-form" onSubmit={handleSubmit} noValidate>
          <div className="form-field">
            <label htmlFor="inspection-title">Inspection title <span>Required</span></label>
            <input id="inspection-title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="e.g. North elevation — level 2" required maxLength={120} />
            <span className="form-field__hint">Use a short name that will be easy to find in your history.</span>
          </div>
          <div className="create-form__grid">
            <div className="form-field">
              <label htmlFor="inspection-location">Building location <span>Optional</span></label>
              <input id="inspection-location" value={location} onChange={(event) => setLocation(event.target.value)} placeholder="Address or site name" />
            </div>
            <div className="form-field">
              <label htmlFor="building-type">Building type <span>Optional</span></label>
              <select id="building-type" value={buildingType} onChange={(event) => setBuildingType(event.target.value)}>
                <option value="">Select a type</option><option>Residential</option><option>Commercial</option><option>Industrial</option><option>Institutional</option><option>Other</option>
              </select>
            </div>
          </div>
          <div className="create-form__grid">
            <div className="form-field">
              <label htmlFor="structure-type">Primary structure type</label>
              <select id="structure-type" value={structure} onChange={(event) => setStructure(event.target.value)}>
                {structureTypes.map((type) => <option key={type}>{type}</option>)}
              </select>
              <span className="form-field__hint">Each photograph can have its own component type in the full product.</span>
            </div>
            <div className="form-field">
              <label htmlFor="inspection-date">Inspection date</label>
              <input id="inspection-date" value={inspectionDate} readOnly />
              <span className="form-field__hint">Set automatically for this prototype.</span>
            </div>
          </div>
          <div className="form-field">
            <label htmlFor="inspection-notes">Inspection notes <span>Optional</span></label>
            <textarea id="inspection-notes" value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Add context for this inspection…" />
          </div>
          {error && <p className="prototype-alert" role="alert">{error}</p>}
          <div className="form-footer">
            <Link className="button button--secondary" to="/app/history">Cancel</Link>
            <button type="submit" className="button button--primary" disabled={!isAuthenticated || !title.trim()}>
              Create draft <ArrowRight size={15} />
            </button>
          </div>
        </form>

        <aside className="create-aside">
          <section className="card card--padded">
            <div className="card-heading"><div><h2>What happens next?</h2><p>A simple, reviewable workflow</p></div></div>
            <div className="create-aside__step"><span className="create-aside__number">1</span><div><strong>Create a draft</strong><p>Your inspection starts in Draft and stays editable.</p></div></div>
            <div className="create-aside__step" style={{ marginTop: 13 }}><span className="create-aside__number">2</span><div><strong>Add photographs</strong><p>Choose wall, beam or column for each photo.</p></div></div>
            <div className="create-aside__step" style={{ marginTop: 13 }}><span className="create-aside__number">3</span><div><strong>Review, then complete</strong><p>Completed inspections are read-only until reopened.</p></div></div>
          </section>
          <SafetyNotice />
          <div className="demo-notice"><ClipboardPlus size={16} /><p>PDF reports and saved records are represented with sample data in this preview.</p></div>
        </aside>
      </div>
    </>
  )
}
