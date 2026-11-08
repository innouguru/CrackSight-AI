import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { DashboardPage } from './DashboardPage'
import { useAuth } from '../hooks/useAuth'
import { apiClient } from '../services/api'
import { ApiError, type Inspection } from '../types'

vi.mock('../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}))

vi.mock('../services/api', () => ({
  apiClient: {
    setToken: vi.fn(),
    listInspections: vi.fn(),
  },
}))

const mockUseAuth = vi.mocked(useAuth)
const mockListInspections = vi.mocked(apiClient.listInspections)

const mockInspections: Inspection[] = [
  {
    id: '00000000-0000-4000-8000-000000000001',
    user_id: 'clerk_user_123',
    title: 'North elevation — level 2',
    building_type: 'Residential',
    building_location: 'Riverside House, Bristol',
    notes: 'Hairline crack above window',
    status: 'draft',
    created_at: '2026-11-02T12:00:00+00:00',
    completed_at: null,
    photograph_count: 4,
  },
  {
    id: '00000000-0000-4000-8000-000000000002',
    user_id: 'clerk_user_123',
    title: 'Loading bay columns',
    building_type: 'Industrial',
    building_location: 'Westgate Works, Bristol',
    notes: null,
    status: 'completed',
    created_at: '2026-10-31T10:00:00+00:00',
    completed_at: '2026-10-31T15:00:00+00:00',
    photograph_count: 8,
  },
  {
    id: '00000000-0000-4000-8000-000000000003',
    user_id: 'clerk_user_123',
    title: 'Plant room beam review',
    building_type: 'Commercial',
    building_location: 'Harbour Point, Bath',
    notes: null,
    status: 'completed',
    created_at: '2026-10-29T14:00:00+00:00',
    completed_at: '2026-10-29T16:00:00+00:00',
    photograph_count: 3,
  },
]

function TestWrapper() {
  return (
    <MemoryRouter initialEntries={['/app']}>
      <DashboardPage />
    </MemoryRouter>
  )
}

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isGuest: false,
      isLoading: false,
      user: { user_id: 'clerk_user_123', email: 'alice@example.com', is_guest: false, is_authenticated: true, guest_session_id: null },
      signIn: vi.fn(),
      signUp: vi.fn(),
      signInWithGoogle: vi.fn(),
      signOut: vi.fn(),
      getToken: vi.fn().mockResolvedValue('clerk-token-123'),
    })
    apiClient.setToken('clerk-token-123')
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the dashboard page', async () => {
    mockListInspections.mockResolvedValue({ inspections: mockInspections, total: 3 })
    render(<TestWrapper />)

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument())
    await waitFor(() => expect(screen.getByText('North elevation — level 2')).toBeInTheDocument())
  })

  it('fetches inspections through the API client with bearer token', async () => {
    let capturedToken: string | null = null
    vi.mocked(apiClient.setToken).mockImplementation((token) => {
      capturedToken = token
    })

    mockListInspections.mockResolvedValue({ inspections: [], total: 0 })
    render(<TestWrapper />)

    await waitFor(() => expect(mockListInspections).toHaveBeenCalledTimes(1))
    expect(mockListInspections).toHaveBeenCalledWith()
    expect(capturedToken).toBe('clerk-token-123')
  })

  it('shows loading state while fetching inspections', async () => {
    let resolveFetch: (value: { inspections: Inspection[]; total: number }) => void = () => {}
    mockListInspections.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFetch = resolve
        }),
    )

    render(<TestWrapper />)

    await waitFor(() => expect(screen.getByText('Loading…')).toBeInTheDocument())
    resolveFetch({ inspections: [], total: 0 })
    await waitFor(() => expect(screen.queryByText('Loading…')).not.toBeInTheDocument())
  })

  it('shows empty state when no inspections exist', async () => {
    mockListInspections.mockResolvedValue({ inspections: [], total: 0 })
    render(<TestWrapper />)

    await waitFor(() => expect(screen.getByText('No inspections yet')).toBeInTheDocument())
  })

  it('shows error state when API request fails', async () => {
    mockListInspections.mockRejectedValue(new ApiError('Server error', 500, 'internal_error', false))
    render(<TestWrapper />)

    await waitFor(() => expect(screen.getByText('Unable to load dashboard')).toBeInTheDocument())
    expect(screen.getByText('Server error')).toBeInTheDocument()
  })

  it('links to inspection detail page', async () => {
    mockListInspections.mockResolvedValue({ inspections: mockInspections, total: 3 })
    render(<TestWrapper />)

    await waitFor(() => expect(screen.getByText('North elevation — level 2')).toBeInTheDocument())

    const link = screen.getByRole('link', { name: /North elevation — level 2/ })
    expect(link).toHaveAttribute('href', '/app/inspections/00000000-0000-4000-8000-000000000001')
  })

  it('does not fetch inspections for guest users', async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isGuest: true,
      isLoading: false,
      user: { user_id: null, email: null, is_guest: true, is_authenticated: false, guest_session_id: 'sess_1' },
      signIn: vi.fn(),
      signUp: vi.fn(),
      signInWithGoogle: vi.fn(),
      signOut: vi.fn(),
      getToken: vi.fn().mockResolvedValue(null),
    })

    render(<TestWrapper />)

    expect(mockListInspections).not.toHaveBeenCalled()
    expect(screen.getByText('You are browsing as a guest. Sign in to save inspections and access your dashboard history.')).toBeInTheDocument()
  })

  it('retries fetching inspections on error when retry button clicked', async () => {
    mockListInspections.mockRejectedValueOnce(new ApiError('Server error', 500, 'internal_error', false))
    render(<TestWrapper />)

    await waitFor(() => expect(screen.getByText('Unable to load dashboard')).toBeInTheDocument())
    expect(screen.getByText('Server error')).toBeInTheDocument()

    mockListInspections.mockResolvedValueOnce({ inspections: mockInspections, total: 3 })
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

    await waitFor(() => expect(screen.getByText('North elevation — level 2')).toBeInTheDocument())
    expect(mockListInspections).toHaveBeenCalledTimes(2)
  })
})
