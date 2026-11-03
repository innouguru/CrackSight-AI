import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'

vi.mock('./hooks/useAuth', () => ({
  useAuth: vi.fn(),
}))

const mockUseAuth = vi.mocked(useAuth)

function TestWrapper({ route = '/' }: { route?: string }) {
  return (
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/" element={<span data-testid="landing">Landing</span>} />
        <Route
          path="/sign-in"
          element={
            <>
              <span data-testid="require-no-auth">{mockUseAuth().isAuthenticated ? 'Authed' : 'Not Authed'}</span>
              <span data-testid="sign-in">Sign In</span>
            </>
          }
        />
        <Route
          path="/app"
          element={
            <>
              {mockUseAuth().isAuthenticated ? (
                <span data-testid="app">App</span>
              ) : (
                <span data-testid="redirect-to-sign-in">Redirecting to sign in</span>
              )}
            </>
          }
        />
        <Route path="*" element={<span data-testid="not-found">Not Found</span>} />
      </Routes>
    </MemoryRouter>
  )
}

describe('Routing', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  function mockAuthState(overrides: Partial<Parameters<typeof mockUseAuth.mockReturnValue>[0]> = {}) {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isGuest: false,
      isLoading: false,
      user: { user_id: null, email: null, is_guest: false, is_authenticated: false, guest_session_id: null },
      signIn: vi.fn(),
      signUp: vi.fn(),
      signInWithGoogle: vi.fn(),
      signOut: vi.fn(),
      getToken: vi.fn().mockResolvedValue(null),
      ...overrides,
    })
  }

  it('renders the landing page at root route', () => {
    mockAuthState()
    render(<TestWrapper route="/" />)
    expect(screen.getByTestId('landing')).toBeInTheDocument()
  })

  it('renders sign-in page without authentication', () => {
    mockAuthState()
    render(<TestWrapper route="/sign-in" />)
    expect(screen.getByTestId('sign-in')).toBeInTheDocument()
  })

  it('does not render app content when accessing /app unauthenticated', () => {
    mockAuthState()
    render(<TestWrapper route="/app" />)
    expect(screen.queryByTestId('app')).not.toBeInTheDocument()
    expect(screen.getByTestId('redirect-to-sign-in')).toBeInTheDocument()
  })

  it('renders app content when accessing /app authenticated', () => {
    mockAuthState({ isAuthenticated: true, isGuest: false })
    render(<TestWrapper route="/app" />)
    expect(screen.getByTestId('app')).toBeInTheDocument()
  })
})
