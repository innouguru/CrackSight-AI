import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { LoadingState } from '../components/LoadingState'
import { ErrorState } from '../components/ErrorState'
import { EmptyState } from '../components/EmptyState'

describe('LoadingState', () => {
  it('renders with default message', () => {
    render(<LoadingState />)
    expect(screen.getByText('Loading…')).toBeInTheDocument()
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('renders with custom message', () => {
    render(<LoadingState message="Checking backend…" />)
    expect(screen.getByText('Checking backend…')).toBeInTheDocument()
  })
})

describe('ErrorState', () => {
  it('renders title and message', () => {
    render(<ErrorState title="Something went wrong" message="Please try again." />)
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
    expect(screen.getByText('Please try again.')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('renders retry button when retryable', () => {
    const onRetry = vi.fn()
    render(<ErrorState title="Error" message="Failed" retryable onRetry={onRetry} />)
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })
})

describe('EmptyState', () => {
  it('renders title and description', () => {
    render(<EmptyState title="No inspections" description="Create an inspection to get started." />)
    expect(screen.getByText('No inspections')).toBeInTheDocument()
    expect(screen.getByText('Create an inspection to get started.')).toBeInTheDocument()
  })

  it('renders action button', () => {
    render(
      <EmptyState title="Empty" action={<button data-testid="empty-action">Create</button>} />,
    )
    expect(screen.getByTestId('empty-action')).toBeInTheDocument()
  })
})
