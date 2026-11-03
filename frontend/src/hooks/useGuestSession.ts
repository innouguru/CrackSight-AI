import { useCallback, useState } from 'react'
import { apiClient } from '../services/api'
import type { GuestSessionCreateResponse, GuestSessionValidateResponse } from '../types'

interface GuestSessionState {
  session: GuestSessionCreateResponse | null
  validation: GuestSessionValidateResponse | null
  isLoading: boolean
  error: string | null
  createSession: () => Promise<void>
  validateSession: (token: string) => Promise<void>
  clearSession: () => void
}

export function useGuestSession(): GuestSessionState {
  const [session, setSession] = useState<GuestSessionCreateResponse | null>(null)
  const [validation, setValidation] = useState<GuestSessionValidateResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const createSession = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await apiClient.createGuestSession()
      setSession(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create guest session')
    } finally {
      setIsLoading(false)
    }
  }, [])

  const validateSession = useCallback(async (token: string) => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await apiClient.validateGuestSession(token)
      setValidation(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to validate guest session')
    } finally {
      setIsLoading(false)
    }
  }, [])

  const clearSession = useCallback(() => {
    setSession(null)
    setValidation(null)
    setError(null)
    apiClient.setGuestSessionToken(null)
  }, [])

  return {
    session,
    validation,
    isLoading,
    error,
    createSession,
    validateSession,
    clearSession,
  }
}
