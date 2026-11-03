import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { apiClient } from '../services/api'
import { ApiError } from '../types'

describe('ApiClient', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    apiClient.setToken(null)
    apiClient.setGuestSessionToken(null)
  })

  afterEach(() => {
    vi.restoreAllMocks()
    globalThis.fetch = originalFetch
  })

  it('should set and clear Clerk bearer token', () => {
    apiClient.setToken('test-token-123')
    expect(apiClient).toBeDefined()
    apiClient.setToken(null)
  })

  it('should set and clear guest session token', () => {
    apiClient.setGuestSessionToken('guest-token-123')
    expect(apiClient).toBeDefined()
    apiClient.setGuestSessionToken(null)
  })

  it('should throw ApiError on non-ok response', async () => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify({ error: 'not_found', message: 'Inspection not found', retryable: false }), {
          status: 404,
          headers: { 'content-type': 'application/json' },
        }),
      ),
    ) as unknown as typeof fetch

    await expect(apiClient.get('/inspections/00000000-0000-0000-0000-000000000000')).rejects.toBeInstanceOf(ApiError)
  })

  it('should throw on network failure', async () => {
    globalThis.fetch = vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))) as unknown as typeof fetch

    await expect(apiClient.health()).rejects.toThrow()
  })

  it('should include Authorization header when token is set', async () => {
    let capturedHeaders: Record<string, string> | null = null
    globalThis.fetch = vi.fn((_url: string, init: RequestInit) => {
      capturedHeaders = init.headers as Record<string, string>
      return Promise.resolve(
        new Response(JSON.stringify({ status: 'ok', service: 'CrackSight AI', version: '0.1.0' }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      )
    }) as unknown as typeof fetch

    apiClient.setToken('clerk-token')
    await apiClient.health()
    apiClient.setToken(null)

    expect(capturedHeaders).toBeDefined()
    expect(capturedHeaders!['Authorization']).toBe('Bearer clerk-token')
  })

  it('should include X-Guest-Session-Token header when guest token is set', async () => {
    let capturedHeaders: Record<string, string> | null = null
    globalThis.fetch = vi.fn((_url: string, init: RequestInit) => {
      capturedHeaders = init.headers as Record<string, string>
      return Promise.resolve(
        new Response(
          JSON.stringify({
            valid: true,
            session_id: '00000000-0000-0000-0000-000000000000',
            analyses_count: 0,
            max_analyses: 3,
            analyses_remaining: 3,
            expires_at: null,
          }),
          { status: 200, headers: { 'content-type': 'application/json' } },
        ),
      )
    }) as unknown as typeof fetch

    apiClient.setGuestSessionToken('guest-token')
    await apiClient.validateGuestSession('guest-token')
    apiClient.setGuestSessionToken(null)

    expect(capturedHeaders).toBeDefined()
    expect(capturedHeaders!['X-Guest-Session-Token']).toBe('guest-token')
  })

  it('should parse health response correctly', async () => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify({ status: 'ok', service: 'CrackSight AI', version: '0.1.0' }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      ),
    ) as unknown as typeof fetch

    const result = await apiClient.health()
    expect(result.status).toBe('ok')
    expect(result.service).toBe('CrackSight AI')
  })

  it('ApiError should have correct properties', () => {
    const err = new ApiError('Something went wrong', 500, 'internal_error', false, 'Retry later')
    expect(err.message).toBe('Something went wrong')
    expect(err.status).toBe(500)
    expect(err.errorCode).toBe('internal_error')
    expect(err.retryable).toBe(false)
    expect(err.action).toBe('Retry later')
    expect(err.name).toBe('ApiError')
  })
})
