interface LoadingStateProps {
  message?: string
  size?: 'sm' | 'md' | 'lg'
}

export function LoadingState({ message = 'Loading…', size = 'md' }: LoadingStateProps) {
  const sizes = {
    sm: { width: 28, height: 28, stroke: 2 },
    md: { width: 40, height: 40, stroke: 3 },
    lg: { width: 56, height: 56, stroke: 4 },
  }
  const s = sizes[size]

  return (
    <div
      className="loading-state"
      role="status"
      aria-label={message}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 12,
        padding: 40,
        textAlign: 'center',
      }}
    >
      <svg
        width={s.width}
        height={s.height}
        viewBox="0 0 50 50"
        fill="none"
        style={{
          animation: 'rotation 0.8s linear infinite',
          color: '#167f78',
        }}
      >
        <circle
          cx="25"
          cy="25"
          r="20"
          stroke="currentColor"
          strokeWidth={s.stroke}
          strokeOpacity={0.15}
        />
        <path
          d="M25 5c2.1 0 4.2 0.5 6.2 1.4"
          stroke="currentColor"
          strokeWidth={s.stroke}
          strokeLinecap="round"
          style={{ animation: 'dash 1.5s ease-in-out infinite' }}
        />
      </svg>
      <p className="loading-state__message">{message}</p>
    </div>
  )
}
