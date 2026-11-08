import { ArrowUpRight, MapPin } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { InspectionView } from '../types'
import { demoImages } from '../data/mockData'
import { StatusPill } from './Ui'

export function InspectionCard({ inspection }: { inspection: InspectionView }) {
  return (
    <article className="card inspection-card">
      <Link to={`/app/inspections/${inspection.id}`} aria-label={`Open ${inspection.title}`}>
        <div className="inspection-card__image">
          <img src={demoImages.original} alt="Sample wall photograph from this inspection" />
          <StatusPill status={inspection.status} />
        </div>
        <div className="inspection-card__body">
          <h3>{inspection.title}</h3>
          <p className="inspection-card__location">
            <MapPin size={12} aria-hidden="true" /> {inspection.location}
          </p>
          <div className="inspection-card__meta">
            <span>
              {inspection.structure ? `${inspection.structure} · ` : ''}
              {inspection.photoCount} photos
            </span>
            <span>{inspection.date}</span>
            <ArrowUpRight size={14} aria-hidden="true" />
          </div>
        </div>
      </Link>
    </article>
  )
}
