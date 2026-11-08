import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { NewInspectionPage } from './NewInspectionPage'
import { useAuth } from '../hooks/useAuth'
import { apiClient } from '../services/api'
import { ApiError } from '../types'

const navigate = vi.fn()

vi.mock('../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}))

vi.mock('../services/api', () => ({
  apiClient: {
    setToken: vi.fn(),
    createInspection: vi.fn(),
  },
}))

vi.mock('react-router-dom', async (importOriginal) => {
  const actual: typeof import('react-router-dom') = await importOriginal()
  return {
    ...actual,
    useNavigate: () => navigate,
  }
})

const mockUseAuth = vi.mocked(useAuth)
const mockCreateInspection = vi.mocked(apiClient.createInspection)

function TestWrapper({ route = '/app/inspections/new' }: { route?: string }) {
  return (
    <MemoryRouter initialEntries={[route]}>
      <NewInspectionPage />
    </MemoryRouter>
  )
}

describe('NewInspectionPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    navigate.mockClear()
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
    mockCreateInspection.mockResolvedValue({
      id: '00000000-0000-4000-8000-000000000090',
      user_id: 'clerk_user_123',
      title: 'North elevation — level 2',
      building_type: 'Residential',
      building_location: null,
      notes: null,
      status: 'draft',
      created_at: '2026-01-01T12:00:00+00:00',
      completed_at: null,
      photograph_count: 0,
    })
    apiClient.setToken('clerk-token-123')
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the inspection creation form with required fields', () => {
    render(<TestWrapper />)
    expect(screen.getByLabelText(/Inspection title/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Building location/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Building type/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Primary structure type/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Inspection notes/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Create draft/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Back to inspections/ })).toBeInTheDocument()
  })

  it('shows validation error when title is empty', async () => {
    render(<TestWrapper />)
    const form = document.querySelector('form')
    expect(form).toBeInTheDocument()
    fireEvent.submit(form!)
    await waitFor(() => expect(screen.getByText('Add an inspection title to continue.')).toBeInTheDocument())
    expect(mockCreateInspection).not.toHaveBeenCalled()
  })

  it('sends the correct payload to the API on valid submission', async () => {
    render(<TestWrapper />)

    const titleInput = screen.getByLabelText(/Inspection title/) as HTMLInputElement
    fireEvent.change(titleInput, { target: { value: 'Facade survey' } })

    const locationInput = screen.getByLabelText(/Building location/) as HTMLInputElement
    fireEvent.change(locationInput, { target: { value: '123 Main St' } })

    const buildingTypeSelect = screen.getByLabelText(/Building type/) as HTMLSelectElement
    fireEvent.change(buildingTypeSelect, { target: { value: 'Residential' } })

    const notesTextarea = screen.getByLabelText(/Inspection notes/) as HTMLTextAreaElement
    fireEvent.change(notesTextarea, { target: { value: 'Hairline crack above window' } })

    fireEvent.click(screen.getByRole('button', { name: /Create draft/ }))

    await waitFor(() => expect(mockCreateInspection).toHaveBeenCalledTimes(1))
    expect(mockCreateInspection).toHaveBeenCalledWith({
      title: 'Facade survey',
      building_type: 'Residential',
      building_location: '123 Main St',
      notes: 'Hairline crack above window',
    })
  })

  it('attaches the Clerk bearer token to the request', async () => {
    let capturedToken: string | null = null
    vi.mocked(apiClient.setToken).mockImplementation((token) => {
      capturedToken = token
    })

    render(<TestWrapper />)

    const titleInput = screen.getByLabelText(/Inspection title/) as HTMLInputElement
    fireEvent.change(titleInput, { target: { value: 'Facade survey' } })
    fireEvent.click(screen.getByRole('button', { name: /Create draft/ }))

    await waitFor(() => expect(mockCreateInspection).toHaveBeenCalled())
    expect(capturedToken).toBe('clerk-token-123')
  })

  it('navigates to the new inspection detail page on success', async () => {
    render(<TestWrapper />)

    const titleInput = screen.getByLabelText(/Inspection title/) as HTMLInputElement
    fireEvent.change(titleInput, { target: { value: 'Facade survey' } })
    fireEvent.click(screen.getByRole('button', { name: /Create draft/ }))

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/app/inspections/00000000-0000-4000-8000-000000000090'))
  })

  it('displays backend validation error on submission failure', async () => {
    mockCreateInspection.mockRejectedValue(
      new ApiError('Inspection title already exists', 400, 'validation_error', false, 'Choose a different title'),
    )

    render(<TestWrapper />)

    const titleInput = screen.getByLabelText(/Inspection title/) as HTMLInputElement
    fireEvent.change(titleInput, { target: { value: 'Facade survey' } })
    fireEvent.click(screen.getByRole('button', { name: /Create draft/ }))

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByRole('alert')).toHaveTextContent('Inspection title already exists')
    expect(mockCreateInspection).toHaveBeenCalledTimes(1)
  })

  it('handles network/server errors', async () => {
    mockCreateInspection.mockRejectedValue(new TypeError('Failed to fetch'))

    render(<TestWrapper />)

    const titleInput = screen.getByLabelText(/Inspection title/) as HTMLInputElement
    fireEvent.change(titleInput, { target: { value: 'Facade survey' } })
    fireEvent.click(screen.getByRole('button', { name: /Create draft/ }))

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByRole('alert')).toHaveTextContent('Failed to create inspection. Please try again.')
  })

  it('prevents duplicate submission while request is pending', async () => {
    let resolveCreate: (value: any) => void = () => {}
    mockCreateInspection.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveCreate = resolve
        }),
    )

    render(<TestWrapper />)

    const titleInput = screen.getByLabelText(/Inspection title/) as HTMLInputElement
    fireEvent.change(titleInput, { target: { value: 'Facade survey' } })

    const submitButton = screen.getByRole('button', { name: /Create draft/ })
    fireEvent.click(submitButton)

    // Click again while pending — should not trigger another call
    fireEvent.click(submitButton)
    expect(mockCreateInspection).toHaveBeenCalledTimes(1)

    resolveCreate({
      id: '00000000-0000-4000-8000-000000000090',
      user_id: 'clerk_user_123',
      title: 'Facade survey',
      building_type: null,
      building_location: null,
      notes: null,
      status: 'draft',
      created_at: '2026-01-01T12:00:00+00:00',
      completed_at: null,
      photograph_count: 0,
    })
    await waitFor(() => expect(mockCreateInspection).toHaveBeenCalledTimes(1))
  })

  it('preserves user-entered values after submission failure', async () => {
    mockCreateInspection.mockRejectedValue(new ApiError('Server error', 500, 'internal_error', false))

    render(<TestWrapper />)

    const titleInput = screen.getByLabelText(/Inspection title/) as HTMLInputElement
    fireEvent.change(titleInput, { target: { value: 'Facade survey' } })
    fireEvent.click(screen.getByRole('button', { name: /Create draft/ }))

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect((titleInput as HTMLInputElement).value).toBe('Facade survey')
  })

  it('shows loading state while submission is in progress', async () => {
    let resolveCreate: (value: any) => void = () => {}
    mockCreateInspection.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveCreate = resolve
        }),
    )

    render(<TestWrapper />)

    const titleInput = screen.getByLabelText(/Inspection title/) as HTMLInputElement
    fireEvent.change(titleInput, { target: { value: 'Facade survey' } })

    const submitButton = screen.getByRole('button', { name: /Create draft/ })
    fireEvent.click(submitButton)

    // Button should show loading state and be disabled (re-query after re-render)
    const submittingButton = screen.getByRole('button', { name: /Creating/ })
    expect(submittingButton).toBeDisabled()
    expect(submittingButton).toHaveTextContent(/Creating/)

    resolveCreate({
      id: '00000000-0000-4000-8000-000000000090',
      user_id: 'clerk_user_123',
      title: 'Facade survey',
      building_type: null,
      building_location: null,
      notes: null,
      status: 'draft',
      created_at: '2026-01-01T12:00:00+00:00',
      completed_at: null,
      photograph_count: 0,
    })
    await waitFor(() => expect(screen.getByRole('button', { name: /Create draft/ })).not.toBeDisabled())
  })
})
