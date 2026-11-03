import type { ReactNode, ComponentType } from 'react'
import { Search } from 'lucide-react'

interface EmptyStateProps {
  title: string
  description?: string
  action?: ReactNode
  icon?: ComponentType<{ size?: number }>
}

export function EmptyState({
  title,
  description,
  action,
  icon: Icon = Search,
}: EmptyStateProps) {
  return (
    <div
      className="empty-state"
      role="status"
      style={{
        display: 'grid',
        minHeight: 230,
        justifyItems: 'center',
        alignContent: 'center',
        padding: 30,
        textAlign: 'center',
      }}
    >
      <span
        className="empty-state__icon"
        style={{
          display: 'grid',
          width: 46,
          height: 46,
          placeItems: 'center',
          marginBottom: 12,
          borderRadius: 14,
          color: '#167f78',
          background: '#eaf5f2',
        }}
      >
        <Icon size={20} />
      </span>
      <h3 className="empty-state__title" style={{ margin: '0 0 8px', color: '#1d2b33', fontSize: 14, fontWeight: 600 }}>
        {title}
      </h3>
      {description && (
        <p className="empty-state__description" style={{ color: '#718087', fontSize: 11, lineHeight: 1.6, maxWidth: 310 }}>
          {description}
        </p>
      )}
      {action && <div style={{ marginTop: 17 }}>{action}</div>}
    </div>
  )
}
