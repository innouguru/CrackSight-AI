import type { ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

interface ErrorStateProps {
  title: string
  message?: string
  action?: ReactNode
  retryable?: boolean
  onRetry?: () => void
}

export function ErrorState({
  title,
  message,
  action,
  retryable = false,
  onRetry,
}: ErrorStateProps) {
  return (
    <div
      className="error-state"
      role="alert"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 16,
        padding: 40,
        textAlign: 'center',
      }}
    >
      <div
        className="error-state__icon"
        style={{
          display: 'grid',
          width: 48,
          height: 48,
          placeItems: 'center',
          borderRadius: 14,
          background: '#faf4f3',
          color: '#bd4d47',
        }}
      >
        <AlertTriangle size={22} />
      </div>
      <h3 className="error-state__title" style={{ margin: 0, color: '#1d2b33', fontSize: 16 }}>
        {title}
      </h3>
      {message && (
        <p className="error-state__message" style={{ color: '#718087', fontSize: 12, lineHeight: 1.6 }}>
          {message}
        </p>
      )}
      {retryable && onRetry && (
        <button
          type="button"
          className="button button--primary"
          onClick={onRetry}
          style={{ minHeight: 39, padding: '0 16px' }}
        >
          <RefreshCw size={14} aria-hidden="true" /> Try again
        </button>
      )}
      {action && <div style={{ marginTop: 12 }}>{action}</div>}
    </div>
  )
}
