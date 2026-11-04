import { useCallback, useState } from 'react'
import { apiClient } from '../services/api'
import type {
  GuestPhotographUploadResponse,
  GuestSessionCreateResponse,
  GuestSessionValidateResponse,
  AnalysisResponse,
} from '../types'

interface GuestSessionState {
  session: GuestSessionCreateResponse | null
  validation: GuestSessionValidateResponse | null
  isLoading: boolean
  error: string | null
  createSession: () => Promise<void>
  validateSession: (token: string) => Promise<void>
  clearSession: () => void
}

interface GuestAnalysisState {
  photograph: GuestPhotographUploadResponse | null
  analysis: AnalysisResponse | null
  isUploading: boolean
  isAnalysing: boolean
  uploadError: string | null
  analysisError: string | null
  uploadPhotograph: (file: File, structureType: string) => Promise<void>
  analysePhotograph: (photoId: string) => Promise<void>
  clearAnalysis: () => void
  analysesRemaining: number
  isSessionValid: boolean
}

export function useGuestSession(): GuestSessionState & GuestAnalysisState {
  const [session, setSession] = useState<GuestSessionCreateResponse | null>(null)
  const [validation, setValidation] = useState<GuestSessionValidateResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [photograph, setPhotograph] = useState<GuestPhotographUploadResponse | null>(null)
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [isAnalysing, setIsAnalysing] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [analysisError, setAnalysisError] = useState<string | null>(null)

  const createSession = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await apiClient.createGuestSession()
      setSession(result)
      apiClient.setGuestSessionToken(result.session_token)
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
      apiClient.setGuestSessionToken(token)
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
    setPhotograph(null)
    setAnalysis(null)
    setUploadError(null)
    setAnalysisError(null)
    apiClient.setGuestSessionToken(null)
  }, [])

  const uploadPhotograph = useCallback(
    async (file: File, structureType: string) => {
      setIsUploading(true)
      setUploadError(null)
      try {
        const result = await apiClient.uploadGuestPhotograph(file, structureType)
        setPhotograph(result)
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to upload photograph.'
        setUploadError(message)
        throw err
      } finally {
        setIsUploading(false)
      }
    },
    [],
  )

  const analysePhotograph = useCallback(
    async (photoId: string) => {
      setIsAnalysing(true)
      setAnalysisError(null)
      try {
        const result = await apiClient.analysePhotograph(photoId)
        setAnalysis(result)
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Analysis failed. Please try again.'
        setAnalysisError(message)
        throw err
      } finally {
        setIsAnalysing(false)
      }
    },
    [],
  )

  const clearAnalysis = useCallback(() => {
    setPhotograph(null)
    setAnalysis(null)
    setUploadError(null)
    setAnalysisError(null)
  }, [])

  const analysesRemaining = validation?.analyses_remaining ?? 0
  const isSessionValid = validation?.valid ?? false

  return {
    session,
    validation,
    isLoading,
    error,
    createSession,
    validateSession,
    clearSession,
    photograph,
    analysis,
    isUploading,
    isAnalysing,
    uploadError,
    analysisError,
    uploadPhotograph,
    analysePhotograph,
    clearAnalysis,
    analysesRemaining,
    isSessionValid,
  }
}
