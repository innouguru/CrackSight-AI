import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { HistoryPage } from './HistoryPage'
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

function TestWrapper({ route = '/app/history' }: { route?: string }) {
  return (
    <MemoryRouter initialEntries={[route]}>
      <HistoryPage />
    </MemoryRouter>
  )
}

describe('HistoryPage', () => {
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

  it('renders the history page with inspections from the backend', async () => {
    mockListInspections.mockResolvedValue({ inspections: mockInspections, total: 3 })
    render(<TestWrapper />)

    await waitFor(() => expect(screen.getByText('North elevation — level 2')).toBeInTheDocument())
    expect(screen.getByText('Loading bay columns')).toBeInTheDocument()
    expect(screen.getByText('Plant room beam review')).toBeInTheDocument()
  })

  it('fetches inspections through the API client with bearer token', async () => {
    let capturedToken: string | null = null
    vi.mocked(apiClient.setToken).mockImplementation((token) => {
      capturedToken = token
    })

    mockListInspections.mockResolvedValue({ inspections: [], total: 0 })
    render(<TestWrapper />)

    await waitFor(() => expect(mockListInspections).toHaveBeenCalledTimes(1))
    expect(mockListInspections).toHaveBeenCalledWith(
      expect.objectContaining({
        search: undefined,
        status: undefined,
        structure_type: undefined,
        verification_status: undefined,
      }),
    )
    expect(capturedToken).toBe('clerk-token-123')
  })

  it('shows loading state while fetching inspections', async () => {
    let resolveFetch: (value: any) => void = () => {}
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

    await waitFor(() => expect(screen.getByText('No inspections match')).toBeInTheDocument())
  })

  it('shows error state when API request fails', async () => {
    mockListInspections.mockRejectedValue(new ApiError('Server error', 500, 'internal_error', false))
    render(<TestWrapper />)

    await waitFor(() => expect(screen.getByText('Unable to load inspection history')).toBeInTheDocument())
    expect(screen.getByText('Server error')).toBeInTheDocument()
  })

  it('switches between list and card views', async () => {
    mockListInspections.mockResolvedValue({ inspections: mockInspections, total: 3 })
    render(<TestWrapper />)

    await waitFor(() => expect(screen.getByText('North elevation — level 2')).toBeInTheDocument())

    expect(screen.getByRole('table')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Card view' }))
    await waitFor(() => expect(screen.getByText('North elevation — level 2')).toBeInTheDocument())
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('filters inspections by title search', async () => {
    mockListInspections.mockResolvedValue({ inspections: mockInspections, total: 3 })
    render(<TestWrapper />)

    await waitFor(() => expect(screen.getByText('Plant room beam review')).toBeInTheDocument())

    const searchInput = screen.getByLabelText('Search inspections')
    fireEvent.change(searchInput, { target: { value: 'beam' } })

    await waitFor(() => {
      expect(screen.getByText('Plant room beam review')).toBeInTheDocument()
      expect(screen.queryByText('North elevation — level 2')).not.toBeInTheDocument()
      expect(screen.queryByText('Loading bay columns')).not.toBeInTheDocument()
    })
  })

  it('filters inspections by status', async () => {
    mockListInspections.mockResolvedValue({ inspections: mockInspections, total: 3 })
    render(<TestWrapper />)

    await waitFor(() => expect(screen.getByText('North elevation — level 2')).toBeInTheDocument())

    const statusSelect = screen.getByLabelText('Filter by status')
    fireEvent.change(statusSelect, { target: { value: 'completed' } })

    await waitFor(() => {
      expect(mockListInspections).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'completed' })
      )
    })
  })

  it('links to inspection detail page from list view', async () => {
    mockListInspections.mockResolvedValue({ inspections: mockInspections, total: 3 })
    render(<TestWrapper />)

    await waitFor(() => expect(screen.getByText('North elevation — level 2')).toBeInTheDocument())

    const link = screen.getByRole('link', { name: /North elevation — level 2/ })
    expect(link).toHaveAttribute('href', '/app/inspections/00000000-0000-4000-8000-000000000001')
  })

  it('navigates to inspection detail page from card view', async () => {
    mockListInspections.mockResolvedValue({ inspections: mockInspections, total: 3 })
    render(<TestWrapper />)

    await waitFor(() => expect(screen.getByText('Loading bay columns')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Card view' }))
    await waitFor(() => expect(screen.getByText('Loading bay columns')).toBeInTheDocument())

    const link = screen.getByRole('link', { name: /Loading bay columns/ })
    expect(link).toHaveAttribute('href', '/app/inspections/00000000-0000-4000-8000-000000000002')
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
    expect(screen.getByText('You are browsing as a guest. Sign in to save inspections and access your inspection history.')).toBeInTheDocument()
  })

  it('retries fetching inspections on error when retry button clicked', async () => {
    mockListInspections.mockRejectedValueOnce(new ApiError('Server error', 500, 'internal_error', false))
    render(<TestWrapper />)

    await waitFor(() => expect(screen.getByText('Unable to load inspection history')).toBeInTheDocument())
    expect(screen.getByText('Server error')).toBeInTheDocument()

    mockListInspections.mockResolvedValueOnce({ inspections: mockInspections, total: 3 })
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

    await waitFor(() => expect(screen.getByText('North elevation — level 2')).toBeInTheDocument())
    expect(mockListInspections).toHaveBeenCalledTimes(2)
  })

  it('structure-type filter interaction', async () => {
    mockListInspections.mockResolvedValue({ inspections: mockInspections, total: 3 })
    render(<TestWrapper />)

    await waitFor(() => expect(screen.getByText('Loading bay columns')).toBeInTheDocument())

    const structureSelect = screen.getByLabelText('Filter by component')
    fireEvent.change(structureSelect, { target: { value: 'wall' } })

    await waitFor(() => {
      expect(mockListInspections).toHaveBeenCalledWith(
        expect.objectContaining({ structure_type: 'wall' })
      )
    })
  })

  it('verification-status filter interaction', async () => {
    mockListInspections.mockResolvedValue({ inspections: mockInspections, total: 3 })
    render(<TestWrapper />)

    await waitFor(() => expect(screen.getByText('North elevation — level 2')).toBeInTheDocument())

    const verificationSelect = screen.getByLabelText('Filter by verification status')
    fireEvent.change(verificationSelect, { target: { value: 'not_verified' } })

    await waitFor(() => {
      expect(mockListInspections).toHaveBeenCalledWith(
        expect.objectContaining({ verification_status: 'not_verified' })
      )
    })
  })

  it('date filter interaction (Last 30 days)', async () => {
    mockListInspections.mockResolvedValue({ inspections: mockInspections, total: 3 })
    render(<TestWrapper />)

    await waitFor(() => expect(screen.getByText('North elevation — level 2')).toBeInTheDocument())

    const dateSelect = screen.getByLabelText('Filter by date')
    fireEvent.change(dateSelect, { target: { value: 'Last 30 days' } })

    await waitFor(() => {
      expect(mockListInspections).toHaveBeenCalledWith(
        expect.objectContaining({
          date_from: expect.any(String),
        })
      )
    })
  })

  it('clears all filters when Clear filters button clicked', async () => {
    mockListInspections.mockResolvedValue({ inspections: mockInspections, total: 3 })
    render(<TestWrapper />)

    await waitFor(() => expect(screen.getByText('Loading bay columns')).toBeInTheDocument())

    const searchInput = screen.getByLabelText('Search inspections')
    fireEvent.change(searchInput, { target: { value: 'column' } })

    await waitFor(() => expect(screen.getByLabelText('Filter by status')).toBeInTheDocument())
    const statusSelect = screen.getByLabelText('Filter by status')
    fireEvent.change(statusSelect, { target: { value: 'completed' } })

    await waitFor(() => expect(screen.getByLabelText('Filter by component')).toBeInTheDocument())
    const structureSelect = screen.getByLabelText('Filter by component')
    fireEvent.change(structureSelect, { target: { value: 'Wall' } })

    await waitFor(() => expect(screen.getByLabelText('Filter by verification status')).toBeInTheDocument())
    const verificationSelect = screen.getByLabelText('Filter by verification status')
    fireEvent.change(verificationSelect, { target: { value: 'correct' } })

    await waitFor(() => expect(screen.getByLabelText('Filter by date')).toBeInTheDocument())
    const dateSelect = screen.getByLabelText('Filter by date')
    fireEvent.change(dateSelect, { target: { value: 'This year' } })

    await waitFor(() => expect(screen.getByRole('button', { name: 'Clear filters' })).toBeInTheDocument())
    const clearButton = screen.getByRole('button', { name: 'Clear filters' })
    fireEvent.click(clearButton)

    await waitFor(() => {
      expect(mockListInspections).toHaveBeenCalledWith(
        expect.objectContaining({
          search: undefined,
          status: undefined,
          structure_type: undefined,
          verification_status: undefined,
        })
      )
    })
  })
})
