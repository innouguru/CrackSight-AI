import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { ArrowRight, Check, CircleAlert, Info } from 'lucide-react'
import type { InspectionStatus, VerificationStatus } from '../data/mockData'

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'quiet'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  leading?: ReactNode
  trailing?: ReactNode
}

export function Button({
  variant = 'primary',
  leading,
  trailing,
  children,
  className = '',
  ...props
}: ButtonProps) {
  return (
    <button className={`button button--${variant} ${className}`} {...props}>
      {leading}
      <span>{children}</span>
      {trailing}
    </button>
  )
}

export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string
  title: string
  description?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p className="page-heading__description">{description}</p>}
      </div>
      {action && <div className="page-heading__action">{action}</div>}
    </div>
  )
}

export function StatusPill({
  status,
  kind = 'inspection',
}: {
  status: InspectionStatus | VerificationStatus
  kind?: 'inspection' | 'verification'
}) {
  const statusClass =
    status === 'Draft'
      ? 'draft'
      : status === 'Completed'
        ? 'completed'
        : status === 'Correct detection'
          ? 'verified'
          : status === 'Partially correct'
            ? 'partial'
            : status === 'Incorrect detection'
              ? 'incorrect'
              : 'unverified'

  return (
    <span className={`status-pill status-pill--${statusClass}`}>
      {kind === 'inspection' && status === 'Completed' ? <Check size={12} /> : null}
      {kind === 'verification' && status === 'Incorrect detection' ? <CircleAlert size={12} /> : null}
      {kind === 'verification' && status === 'Not verified' ? <Info size={12} /> : null}
      {status}
    </span>
  )
}

export function DemoNotice({ children }: { children: ReactNode }) {
  return (
    <div className="demo-notice" role="note">
      <Info size={16} aria-hidden="true" />
      <p>{children}</p>
    </div>
  )
}

export function SafetyNotice({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`safety-notice${compact ? ' safety-notice--compact' : ''}`}>
      <span className="safety-notice__icon">
        <CircleAlert size={17} />
      </span>
      <p>
        <strong>Inspection aid only.</strong> AI predictions require human review and do not assess
        structural safety or replace a qualified engineer.
      </p>
    </div>
  )
}

export function LinkArrow() {
  return <ArrowRight size={16} aria-hidden="true" />
}
