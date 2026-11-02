import {
  ArrowRight,
  ArrowUpRight,
  ClipboardPlus,
  FileText,
  ImagePlus,
  Images,
  Search,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { DemoNotice, PageHeading, SafetyNotice, StatusPill } from '../components/Ui'
import { usePrototype } from '../data/usePrototype'
import { demoImages } from '../data/mockData'

export function DashboardPage() {
  const { inspections } = usePrototype()
  const recent = inspections.slice(0, 3)

  return (
    <>
      <PageHeading
        eyebrow="Monday, 2 November 2026"
        title="Good morning, Jordan"
        description="Here’s an overview of your inspection workspace."
        action={<Link className="button button--primary" to="/app/inspections/new"><ClipboardPlus size={16} /> New inspection</Link>}
      />
      <DemoNotice>
        You’re viewing sample workspace data. Changes in this prototype stay in memory and aren’t saved to a server.
      </DemoNotice>
      <div className="metrics-grid" style={{ marginTop: 15 }}>
        <article className="card metric-card">
          <div className="metric-card__top"><span>Total inspections</span><span className="metric-card__icon"><ClipboardPlus size={15} /></span></div>
          <p className="metric-card__value">12</p><p className="metric-card__note">Across 4 locations</p>
        </article>
        <article className="card metric-card">
          <div className="metric-card__top"><span>Photos analysed</span><span className="metric-card__icon"><Images size={15} /></span></div>
          <p className="metric-card__value">47</p><p className="metric-card__note">Across all inspections</p>
        </article>
        <article className="card metric-card">
          <div className="metric-card__top"><span>Draft inspections</span><span className="metric-card__icon"><FileText size={15} /></span></div>
          <p className="metric-card__value">{inspections.filter((inspection) => inspection.status === 'Draft').length}</p><p className="metric-card__note">Ready for your review</p>
        </article>
        <article className="card metric-card">
          <div className="metric-card__top"><span>Analyses this month</span><span className="metric-card__icon"><ImagePlus size={15} /></span></div>
          <p className="metric-card__value">18 <span style={{ color: '#94a0a5', fontSize: 13, fontWeight: 500 }}>/ 100</span></p><p className="metric-card__note">Monthly allowance</p>
        </article>
      </div>

      <div className="dashboard-grid">
        <section className="card card--padded">
          <div className="card-heading">
            <div><h2>Recent inspections</h2><p>Your latest inspection activity</p></div>
            <Link className="card-heading__action" to="/app/history">View all <ArrowRight size={13} /></Link>
          </div>
          <div className="recent-list">
            {recent.length > 0 ? recent.map((inspection) => (
              <Link className="recent-row" to={`/app/inspections/${inspection.id}`} key={inspection.id}>
                <span className="recent-row__main">
                  <span className="recent-row__thumb"><img src={demoImages.original} alt="" /></span>
                  <span>
                    <span className="recent-row__title">{inspection.title}</span>
                    <span className="recent-row__location">{inspection.location}</span>
                  </span>
                </span>
                <StatusPill status={inspection.status} />
                <span className="recent-row__date">{inspection.date}<ArrowUpRight size={13} /></span>
              </Link>
            )) : (
              <div className="empty-state"><span className="empty-state__icon"><Search size={20} /></span><h3>No inspections yet</h3><p>Create an inspection to start organizing your building photographs.</p><Link className="button button--primary" to="/app/inspections/new">Create inspection</Link></div>
            )}
          </div>
        </section>

        <aside className="card card--padded">
          <div className="card-heading"><div><h2>Quick actions</h2><p>Pick up where you left off</p></div></div>
          <div className="quick-actions">
            <Link className="quick-action" to="/app/inspections/new">
              <span className="quick-action__icon"><ClipboardPlus size={16} /></span>
              <span className="quick-action__text"><strong>Start an inspection</strong><small>Record a new building visit</small></span><ArrowRight size={14} />
            </Link>
            <Link className="quick-action" to="/try">
              <span className="quick-action__icon"><ImagePlus size={16} /></span>
              <span className="quick-action__text"><strong>Try a guest analysis</strong><small>Explore image review screens</small></span><ArrowRight size={14} />
            </Link>
            <Link className="quick-action" to="/app/reports">
              <span className="quick-action__icon"><FileText size={16} /></span>
              <span className="quick-action__text"><strong>View reports</strong><small>Browse sample PDF previews</small></span><ArrowRight size={14} />
            </Link>
          </div>
          <div className="dashboard-safety"><SafetyNotice compact /></div>
        </aside>
      </div>
    </>
  )
}
