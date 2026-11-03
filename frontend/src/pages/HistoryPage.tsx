import { CalendarDays, LayoutGrid, List, Plus, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { InspectionCard } from '../components/InspectionCard'
import { DemoNotice, PageHeading, StatusPill } from '../components/Ui'
import { useAuth } from '../hooks/useAuth'
import { initialInspections, type Inspection } from '../data/mockData'

type ViewMode = 'cards' | 'list'

function isWithinDateRange(dateLabel: string, range: string) {
  if (range === 'Any date') return true
  const date = new Date(`${dateLabel} 00:00:00`)
  if (Number.isNaN(date.getTime())) return true
  const ageInDays = (Date.now() - date.getTime()) / (1000 * 60 * 60 * 24)
  if (range === 'Last 30 days') return ageInDays <= 30
  if (range === 'This year') return date.getFullYear() === new Date().getFullYear()
  return true
}

function InspectionTable({ inspections }: { inspections: Inspection[] }) {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead><tr><th>Inspection</th><th>Location</th><th>Component</th><th>Photos</th><th>Status</th><th>Date</th></tr></thead>
        <tbody>
          {inspections.map((inspection) => (
            <tr key={inspection.id}>
              <td><Link className="table-primary" to={`/app/inspections/${inspection.id}`}>{inspection.title}</Link></td>
              <td>{inspection.location}</td><td>{inspection.structure}</td><td>{inspection.photoCount}</td>
              <td><StatusPill status={inspection.status} /></td><td>{inspection.date}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function HistoryPage() {
  const { isLoading } = useAuth()
  const inspections = initialInspections
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('All statuses')
  const [structure, setStructure] = useState('All components')
  const [dateRange, setDateRange] = useState('Any date')
  const [view, setView] = useState<ViewMode>('list')

  const filtered = useMemo(
    () =>
      inspections.filter((inspection) => {
        const matchesQuery =
          `${inspection.title} ${inspection.location}`.toLowerCase().includes(query.toLowerCase())
        return (
          matchesQuery &&
          (status === 'All statuses' || inspection.status === status) &&
          (structure === 'All components' || inspection.structure === structure) &&
          isWithinDateRange(inspection.date, dateRange)
        )
      }),
    [dateRange, inspections, query, status, structure],
  )

  return (
    <>
      <PageHeading
        eyebrow="Inspection records"
        title="Inspection history"
        description="Search and review your saved building inspections."
        action={<Link className="button button--primary" to="/app/inspections/new"><Plus size={16} /> New inspection</Link>}
      />
      <DemoNotice>
        {isLoading ? 'Resolving your session…' : 'History is powered by sample data. Inspection records will be connected to your account in the next milestone.'}
      </DemoNotice>
      <div className="history-toolbar" style={{ marginTop: 16 }}>
        <div className="history-toolbar__filters">
          <label className="search-control">
            <Search size={15} aria-hidden="true" />
            <input aria-label="Search inspections" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search title or location…" />
          </label>
          <select className="filter-select" aria-label="Filter by status" value={status} onChange={(event) => setStatus(event.target.value)}>
            <option>All statuses</option><option>Draft</option><option>Completed</option>
          </select>
          <select className="filter-select" aria-label="Filter by component" value={structure} onChange={(event) => setStructure(event.target.value)}>
            <option>All components</option><option>Wall</option><option>Beam</option><option>Column</option>
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
          <div className="empty-state"><span className="empty-state__icon"><CalendarDays size={20} /></span><h3>No inspections match</h3><p>Try changing your search or filters to find another inspection.</p><button className="button button--secondary" onClick={() => { setQuery(''); setStatus('All statuses'); setStructure('All components'); setDateRange('Any date') }}>Clear filters</button></div>
        ) : view === 'list' ? <InspectionTable inspections={filtered} /> : (
          <div className="inspection-cards" style={{ padding: 14 }}>
            {filtered.map((inspection) => <InspectionCard key={inspection.id} inspection={inspection} />)}
          </div>
        )}
      </section>
    </>
  )
}
