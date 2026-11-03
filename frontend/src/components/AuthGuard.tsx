import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { LoadingState } from './LoadingState'
import { useAuth } from '../hooks/useAuth'

interface AuthGuardProps {
  children: (props: { isAuthenticated: boolean; isLoading: boolean }) => ReactNode
  redirectTo?: string
}

export function AuthGuard({
  children,
  redirectTo = '/sign-in',
}: AuthGuardProps) {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return <LoadingState message="Resolving session…" />
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to={redirectTo}
        replace
        state={{ from: location.pathname }}
      />
    )
  }

  return children({ isAuthenticated, isLoading })
}

interface GuestOnlyGuardProps {
  children: (props: { isGuest: boolean; isLoading: boolean }) => ReactNode
  redirectTo?: string
}

export function GuestOnlyGuard({
  children,
  redirectTo = '/app',
}: GuestOnlyGuardProps) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <LoadingState message="Resolving session…" />
  }

  if (isAuthenticated) {
    return <Navigate to={redirectTo} replace />
  }

  return children({ isGuest: true, isLoading })
}

interface PublicGuardProps {
  children: (props: { isAuthenticated: boolean; isLoading: boolean }) => ReactNode
}

export function PublicGuard({ children }: PublicGuardProps) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <LoadingState message="Resolving session…" />
  }

  return children({ isAuthenticated, isLoading })
}
