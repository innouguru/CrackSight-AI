import { CalendarDays, LayoutGrid, List, Plus, Search } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, type Inspection, type InspectionView } from '../types'
import { apiClient } from '../services/api'
import { InspectionCard } from '../components/InspectionCard'
import { DemoNotice, PageHeading, StatusPill } from '../components/Ui'
import { ErrorState } from '../components/ErrorState'
import { LoadingState } from '../components/LoadingState'
import { useAuth } from '../hooks/useAuth'

type ViewMode = 'cards' | 'list'

function formatInspectionDate(isoString: string): string {
  return new Date(isoString).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

function toInspectionView(insp: Inspection): InspectionView {
  return {
    id: insp.id,
    title: insp.title,
    location: insp.building_location,
    buildingType: insp.building_type,
    date: formatInspectionDate(insp.created_at),
    status: insp.status === 'completed' ? 'Completed' : 'Draft',
    photoCount: insp.photograph_count,
    notes: insp.notes,
  }
}

function InspectionTable({ inspections }: { inspections: InspectionView[] }) {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead><tr><th>Inspection</th><th>Location</th><th>Component</th><th>Photos</th><th>Status</th><th>Date</th></tr></thead>
        <tbody>
          {inspections.map((inspection) => (
            <tr key={inspection.id}>
              <td><Link className="table-primary" to={`/app/inspections/${inspection.id}`}>{inspection.title}</Link></td>
              <td>{inspection.location}</td><td>{inspection.structure ?? '—'}</td><td>{inspection.photoCount}</td>
              <td><StatusPill status={inspection.status} /></td><td>{inspection.date}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function HistoryPage() {
  const { isAuthenticated, isGuest, isLoading: authLoading, getToken } = useAuth()
  const [inspections, setInspections] = useState<InspectionView[]>([])
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('All statuses')
  const [structure, setStructure] = useState('All components')
  const [verification, setVerification] = useState('All verification statuses')
  const [dateRange, setDateRange] = useState('Any date')
  const [view, setView] = useState<ViewMode>('list')
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
      const dateParams =
        dateRange === 'Last 30 days'
          ? { date_from: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0] }
          : dateRange === 'This year'
            ? {
                date_from: `${new Date().getFullYear()}-01-01`,
                date_to: `${new Date().getFullYear()}-12-31`,
              }
            : {}
      const response = await apiClient.listInspections({
        search: query || undefined,
        status: status === 'All statuses' ? undefined : status.toLowerCase(),
        structure_type: structure === 'All components' ? undefined : structure.toLowerCase(),
        verification_status: verification === 'All verification statuses' ? undefined : verification,
        ...dateParams,
      })
      setInspections(response.inspections.map(toInspectionView))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load inspections.')
    } finally {
      setLoading(false)
    }
  }, [isAuthenticated, isGuest, query, status, structure, verification, dateRange])

  useEffect(() => {
    fetchInspections()
  }, [fetchInspections])

  const filtered = useMemo(() => {
    return inspections.filter((inspection) => {
      const matchesQuery =
        `${inspection.title} ${inspection.location}`.toLowerCase().includes(query.toLowerCase())
      const matchesStatus = status === 'All statuses' || inspection.status === status
      return matchesQuery && matchesStatus
    })
  }, [inspections, query, status])

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
          eyebrow="Inspection records"
          title="Inspection history"
          description="Search and review your saved building inspections."
          action={<Link className="button button--primary" to="/app/inspections/new"><Plus size={16} /> New inspection</Link>}
        />
        <DemoNotice>
          You are browsing as a guest. Sign in to save inspections and access your inspection history.
        </DemoNotice>
      </>
    )
  }

  if (error) {
    return (
      <div className="app-content" style={{ padding: 40 }}>
        <ErrorState
          title="Unable to load inspection history"
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
        eyebrow="Inspection records"
        title="Inspection history"
        description="Search and review your saved building inspections."
        action={<Link className="button button--primary" to="/app/inspections/new"><Plus size={16} /> New inspection</Link>}
      />
      {!loading && inspections.length === 0 && (
        <DemoNotice>No inspections yet. Create an inspection to get started.</DemoNotice>
      )}
      <div className="history-toolbar" style={{ marginTop: 16 }}>
        <div className="history-toolbar__filters">
          <label className="search-control">
            <Search size={15} aria-hidden="true" />
            <input aria-label="Search inspections" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search title or location…" />
          </label>
          <select className="filter-select" aria-label="Filter by status" value={status} onChange={(event) => setStatus(event.target.value)}>
            <option>All statuses</option><option value="draft">Draft</option><option value="completed">Completed</option>
          </select>
          <select className="filter-select" aria-label="Filter by component" value={structure} onChange={(event) => setStructure(event.target.value)}>
            <option>All components</option><option value="wall">Wall</option><option value="beam">Beam</option><option value="column">Column</option>
          </select>
          <select className="filter-select" aria-label="Filter by verification status" value={verification} onChange={(event) => setVerification(event.target.value)}>
            <option>All verification statuses</option><option value="not_verified">Not verified</option><option value="correct">Correct</option><option value="incorrect">Incorrect</option><option value="partial">Partial</option>
          </select>
          <select className="filter-select" aria-label="Filter by date" value={dateRange} onChange={(event) => setDateRange(event.target.value)}>
            <option>Any date</option><option>Last 30 days</option><option>This year</option>
          </select>
        </div>
        <div className="view-toggle" aria-label="Inspection layout">
          <button type="button" className={view === 'list' ? 'is-active' : ''} onClick={() => setView('list')} aria-label="List view"><List size={16} /></button>
          <button type="button" className={view === 'cards' ? 'is-active' : ''} onClick={() => setView('cards')} aria-label="Card view"><LayoutGrid size={15} /></button>
        </div>
      </div>
      <section className="card">
        {filtered.length === 0 ? (
          <div className="empty-state"><span className="empty-state__icon"><CalendarDays size={20} /></span><h3>No inspections match</h3><p>Try changing your search or filters to find another inspection.</p><button className="button button--secondary" onClick={() => { setQuery(''); setStatus('All statuses'); setStructure('All components'); setVerification('All verification statuses'); setDateRange('Any date') }}>Clear filters</button></div>
        ) : view === 'list' ? <InspectionTable inspections={filtered} /> : (
          <div className="inspection-cards" style={{ padding: 14 }}>
            {filtered.map((inspection) => <InspectionCard key={inspection.id} inspection={inspection} />)}
          </div>
        )}
      </section>
    </>
  )
}
