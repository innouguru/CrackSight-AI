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

  it('listInspections passes all filter parameters to the query string', async () => {
    let capturedUrl: string | null = null
    globalThis.fetch = vi.fn((url: string) => {
      capturedUrl = url
      return Promise.resolve(
        new Response(
          JSON.stringify({
            inspections: [],
            total: 0,
          }),
          { status: 200, headers: { 'content-type': 'application/json' } },
        ),
      )
    }) as unknown as typeof fetch

    await apiClient.listInspections({
      search: 'test',
      status: 'completed',
      structure_type: 'wall',
      verification_status: 'correct',
      date_from: '2026-01-01',
      date_to: '2026-12-31',
      limit: 10,
      offset: 5,
    })

    expect(capturedUrl).toContain('search=test')
    expect(capturedUrl).toContain('status=completed')
    expect(capturedUrl).toContain('structure_type=wall')
    expect(capturedUrl).toContain('verification_status=correct')
    expect(capturedUrl).toContain('date_from=2026-01-01')
    expect(capturedUrl).toContain('date_to=2026-12-31')
    expect(capturedUrl).toContain('limit=10')
    expect(capturedUrl).toContain('offset=5')
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

  describe('uploadPhotograph', () => {
    const inspectionId = '3f1d2b4e-0000-4000-8000-000000000001'

    it('sends multipart form data with file and structure type and bearer token', async () => {
      let capturedUrl: string | null = null
      let capturedMethod: string | null = null
      let capturedHeaders: Record<string, string> | null = null
      let capturedBody: FormData | null = null
      globalThis.fetch = vi.fn((_url: string, init: RequestInit) => {
        capturedUrl = _url
        capturedMethod = init.method as string
        capturedHeaders = init.headers as Record<string, string>
        capturedBody = init.body as FormData
        return Promise.resolve(
          new Response(
            JSON.stringify({
              id: '00000000-0000-4000-8000-000000000090',
              inspection_id: inspectionId,
              user_id: 'clerk_user_123',
              structure_type: 'wall',
              observation: null,
              verification_status: 'not_verified',
              original_image_key: `inspections/${inspectionId}/originals/photo.jpg`,
              prediction_mask_key: null,
              prediction_overlay_key: null,
              model_version: null,
              prediction_timestamp: null,
              pixel_measurements: null,
              created_at: '2026-01-01T12:00:00+00:00',
            }),
            { status: 201, headers: { 'content-type': 'application/json' } },
          ),
        )
      }) as unknown as typeof fetch

      const file = new File(['fake-bytes'], 'wall.jpg', { type: 'image/jpeg' })
      apiClient.setToken('clerk-token')
      await apiClient.uploadPhotograph(inspectionId, file, 'wall')
      apiClient.setToken(null)

      expect(capturedUrl).toBe(`http://127.0.0.1:8000/photos/${inspectionId}/upload`)
      expect(capturedMethod).toBe('POST')
      expect(capturedHeaders).toMatchObject({ Authorization: 'Bearer clerk-token' })
      expect(capturedBody as unknown as FormData).toBeInstanceOf(FormData)
      expect((capturedBody as unknown as FormData).get('file')).toBe(file)
      expect((capturedBody as unknown as FormData).get('structure_type')).toBe('wall')
    })

    it('throws ApiError when upload fails', async () => {
      globalThis.fetch = vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({ error: 'validation_error', message: 'Invalid image content', retryable: false }),
            { status: 400, headers: { 'content-type': 'application/json' } },
          ),
        ),
      ) as unknown as typeof fetch

      const file = new File(['not-an-image'], 'corrupt.jpg', { type: 'image/jpeg' })
      await expect(apiClient.uploadPhotograph(inspectionId, file, 'wall')).rejects.toBeInstanceOf(ApiError)
    })
  })

  describe('listInspectionPhotographs', () => {
    it('fetches photographs for the inspection', async () => {
      let capturedUrl: string | null = null
      globalThis.fetch = vi.fn((url: string) => {
        capturedUrl = url
        return Promise.resolve(
          new Response(
            JSON.stringify({
              inspection_id: '3f1d2b4e-0000-4000-8000-000000000001',
              photographs: [],
              total: 0,
            }),
            { status: 200, headers: { 'content-type': 'application/json' } },
          ),
        )
      }) as unknown as typeof fetch

      await apiClient.listInspectionPhotographs('3f1d2b4e-0000-4000-8000-000000000001')
      expect(capturedUrl).toBe('http://127.0.0.1:8000/inspections/3f1d2b4e-0000-4000-8000-000000000001/photos')
    })
  })

  describe('downloadPhotographImage', () => {
    it('returns a blob URL for the original image and sends the bearer token', async () => {
      const originalCreateObjectURL = globalThis.URL.createObjectURL
      globalThis.URL.createObjectURL = vi.fn(() => 'blob:mock-url') as typeof globalThis.URL.createObjectURL
      let capturedUrl: string | null = null
      let capturedAuth: string | null = null
      globalThis.fetch = vi.fn((_url: string, init: RequestInit) => {
        capturedUrl = _url
        capturedAuth = (init.headers as Record<string, string>)?.Authorization ?? null
        return Promise.resolve(
          new Response(new Uint8Array([1, 2, 3]), {
            status: 200,
            headers: { 'content-type': 'image/jpeg' },
          }),
        )
      }) as unknown as typeof fetch

      apiClient.setToken('clerk-token')
      const blobUrl = await apiClient.downloadPhotographImage('00000000-0000-4000-8000-000000000090', 'original')
      apiClient.setToken(null)

      expect(capturedUrl).toBe('http://127.0.0.1:8000/photos/00000000-0000-4000-8000-000000000090/download/original')
      expect(capturedAuth).toBe('Bearer clerk-token')
      expect(blobUrl).toBe('blob:mock-url')
      globalThis.URL.createObjectURL = originalCreateObjectURL
    })
  })

  describe('generateReport', () => {
    it('posts to the generate endpoint with the bearer token', async () => {
      let capturedUrl: string | null = null
      let capturedMethod: string | null = null
      let capturedAuth: string | null = null
      globalThis.fetch = vi.fn((url: string, init: RequestInit) => {
        capturedUrl = url
        capturedMethod = init.method ?? null
        capturedAuth = (init.headers as Record<string, string>)?.Authorization ?? null
        return Promise.resolve(
          new Response(
            JSON.stringify({
              report_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
              generated_at: '2026-11-08T12:00:00+00:00',
              download_url: '/reports/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/download',
            }),
            { status: 200, headers: { 'content-type': 'application/json' } },
          ),
        )
      }) as unknown as typeof fetch

      apiClient.setToken('clerk-token')
      const report = await apiClient.generateReport('11111111-2222-4333-8444-555555555555')
      apiClient.setToken(null)

      expect(capturedUrl).toBe('http://127.0.0.1:8000/reports/generate/11111111-2222-4333-8444-555555555555')
      expect(capturedMethod).toBe('POST')
      expect(capturedAuth).toBe('Bearer clerk-token')
      expect(report.report_id).toBe('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa')
      expect(report.download_url).toBe('/reports/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/download')
    })

    it('throws ApiError on a 404 response', async () => {
      globalThis.fetch = vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({ error: 'not_found', message: 'Inspection not found', retryable: false }),
            { status: 404, headers: { 'content-type': 'application/json' } },
          ),
        ),
      ) as unknown as typeof fetch

      await expect(apiClient.generateReport('00000000-0000-0000-0000-000000000000')).rejects.toMatchObject({
        status: 404,
        message: 'Inspection not found',
      })
    })
  })

  describe('downloadReportPdf', () => {
    it('returns a blob URL for the PDF and sends the bearer token', async () => {
      const originalCreateObjectURL = globalThis.URL.createObjectURL
      globalThis.URL.createObjectURL = vi.fn(() => 'blob:pdf-mock-url') as typeof globalThis.URL.createObjectURL
      let capturedUrl: string | null = null
      let capturedAuth: string | null = null
      globalThis.fetch = vi.fn((_url: string, init: RequestInit) => {
        capturedUrl = _url
        capturedAuth = (init.headers as Record<string, string>)?.Authorization ?? null
        return Promise.resolve(
          new Response(new Uint8Array([0x25, 0x50, 0x44, 0x46]), {
            status: 200,
            headers: { 'content-type': 'application/pdf' },
          }),
        )
      }) as unknown as typeof fetch

      apiClient.setToken('clerk-token')
      const blobUrl = await apiClient.downloadReportPdf('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa')
      apiClient.setToken(null)

      expect(capturedUrl).toBe('http://127.0.0.1:8000/reports/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/download')
      expect(capturedAuth).toBe('Bearer clerk-token')
      expect(blobUrl).toBe('blob:pdf-mock-url')
      globalThis.URL.createObjectURL = originalCreateObjectURL
    })

    it('throws ApiError on a JSON error response', async () => {
      const originalCreateObjectURL = globalThis.URL.createObjectURL
      globalThis.URL.createObjectURL = vi.fn(() => 'blob:unused') as typeof globalThis.URL.createObjectURL
      globalThis.fetch = vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({ error: 'not_found', message: 'Report not found', retryable: false }),
            { status: 404, headers: { 'content-type': 'application/json' } },
          ),
        ),
      ) as unknown as typeof fetch

      await expect(apiClient.downloadReportPdf('00000000-0000-0000-0000-000000000000')).rejects.toMatchObject({
        status: 404,
        message: 'Report not found',
      })
      globalThis.URL.createObjectURL = originalCreateObjectURL
    })
  })
})
