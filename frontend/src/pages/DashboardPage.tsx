import {
  ArrowRight,
  ArrowUpRight,
  ClipboardPlus,
  FileText,
  ImagePlus,
  Images,
  Search,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, type InspectionView, toInspectionView } from '../types'
import { apiClient } from '../services/api'
import { DemoNotice, PageHeading, SafetyNotice, StatusPill } from '../components/Ui'
import { ErrorState } from '../components/ErrorState'
import { LoadingState } from '../components/LoadingState'
import { useAuth } from '../hooks/useAuth'

export function DashboardPage() {
  const { isAuthenticated, isGuest, isLoading: authLoading, getToken } = useAuth()
  const [inspections, setInspections] = useState<InspectionView[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Attach the Clerk bearer token to the API client once auth resolves.
  useEffect(() => {
    ;(async () => {
      const token = await getToken()
      apiClient.setToken(token ?? null)
    })()
  }, [getToken])

  const fetchInspections = useCallback(async () => {
    if (!isAuthenticated || isGuest) {
      setInspections([])
      return
    }
    setLoading(true)
    setError(null)
    try {
      const response = await apiClient.listInspections()
      setInspections(response.inspections.map(toInspectionView))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load inspections.')
    } finally {
      setLoading(false)
    }
  }, [isAuthenticated, isGuest])

  useEffect(() => {
    fetchInspections()
  }, [fetchInspections])

  const totalInspections = inspections.length
  const totalPhotographs = inspections.reduce((sum, insp) => sum + insp.photoCount, 0)
  const draftCount = inspections.filter((i) => i.status === 'Draft').length
  const recent = inspections.slice(0, 3)

  if (authLoading || loading) {
    return (
      <div className="app-content" style={{ padding: 40, display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center' }}>
        <LoadingState message="Loading…" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <>
        <PageHeading
          eyebrow="Dashboard"
          title="Dashboard"
          description="Here’s an overview of your inspection workspace."
          action={<Link className="button button--primary" to="/app/inspections/new"><ClipboardPlus size={16} /> New inspection</Link>}
        />
        <DemoNotice>
          You are browsing as a guest. Sign in to save inspections and access your dashboard history.
        </DemoNotice>
      </>
    )
  }

  if (error) {
    return (
      <div className="app-content" style={{ padding: 40 }}>
        <ErrorState
          title="Unable to load dashboard"
          message={error}
          retryable
          onRetry={fetchInspections}
        />
      </div>
    )
  }

  return (
    <>
      <PageHeading
        eyebrow="Dashboard"
        title="Dashboard"
        description="Here’s an overview of your inspection workspace."
        action={<Link className="button button--primary" to="/app/inspections/new"><ClipboardPlus size={16} /> New inspection</Link>}
      />
      {!loading && inspections.length === 0 && (
        <DemoNotice>No inspections yet. Create an inspection to get started.</DemoNotice>
      )}
      <div className="metrics-grid" style={{ marginTop: 15 }}>
        <article className="card metric-card">
          <div className="metric-card__top"><span>Total inspections</span><span className="metric-card__icon"><ClipboardPlus size={15} /></span></div>
          <p className="metric-card__value">{totalInspections}</p><p className="metric-card__note">{totalInspections === 1 ? 'inspection' : 'inspections'}</p>
        </article>
        <article className="card metric-card">
          <div className="metric-card__top"><span>Photos analysed</span><span className="metric-card__icon"><Images size={15} /></span></div>
          <p className="metric-card__value">{totalPhotographs}</p><p className="metric-card__note">Across all inspections</p>
        </article>
        <article className="card metric-card">
          <div className="metric-card__top"><span>Draft inspections</span><span className="metric-card__icon"><FileText size={15} /></span></div>
          <p className="metric-card__value">{draftCount}</p><p className="metric-card__note">Ready for your review</p>
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
                  <span className="recent-row__thumb"><img src="/demo/crack-wall.jpg" alt="" /></span>
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
