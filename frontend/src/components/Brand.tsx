import { Activity } from 'lucide-react'

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <span className={`brand${compact ? ' brand--compact' : ''}`}>
      <span className="brand__mark" aria-hidden="true">
        <Activity size={19} strokeWidth={2.2} />
      </span>
      {!compact && (
        <span className="brand__wordmark">
          CrackSight <span>AI</span>
        </span>
      )}
    </span>
  )
}
