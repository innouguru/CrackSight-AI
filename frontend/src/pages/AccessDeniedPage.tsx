import { ArrowLeft, LockKeyhole } from 'lucide-react'
import { Link } from 'react-router-dom'
import { DemoNotice, SafetyNotice } from '../components/Ui'

export function AccessDeniedPage() {
  return (
    <section className="card card--padded access-denied">
      <span className="empty-state__icon"><LockKeyhole size={21} /></span>
      <p className="eyebrow">Access control · sample state</p>
      <h1>Access to this inspection is unavailable</h1>
      <p className="page-heading__description">This account doesn’t have permission to view the requested record. Check that you’re signed in with the account that owns the inspection.</p>
      <DemoNotice>This is a static access-denied example. Real ownership checks remain enforced by the FastAPI backend when integrated.</DemoNotice>
      <div className="access-denied__actions">
        <Link className="button button--secondary" to="/app"><ArrowLeft size={14} /> Back to workspace</Link>
        <Link className="button button--quiet" to="/sign-in">Sign in with another account</Link>
      </div>
      <SafetyNotice />
    </section>
  )
}
