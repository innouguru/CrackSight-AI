import { useCallback, useEffect, useState } from 'react'
import { apiClient } from '../services/api'
import type { HealthResponse } from '../types'

interface ApiStatus {
  isOnline: boolean
  isLoading: boolean
  error: string | null
  health: HealthResponse | null
  checkHealth: () => Promise<void>
}

export function useApiStatus(): ApiStatus {
  const [isOnline, setIsOnline] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [health, setHealth] = useState<HealthResponse | null>(null)

  const checkHealth = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await apiClient.health()
      setHealth(result)
      setIsOnline(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Backend is unreachable')
      setIsOnline(false)
      setHealth(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void checkHealth()
  }, [checkHealth])

  return { isOnline, isLoading, error, health, checkHealth }
}
