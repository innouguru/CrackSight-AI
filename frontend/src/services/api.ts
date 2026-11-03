import { ApiError } from '../types'
import type {
  AnalysisResponse,
  ApiErrorBody,
  GuestAnalysisConsumeResponse,
  GuestSessionCreateResponse,
  GuestSessionValidateResponse,
  HealthResponse,
  Inspection,
  InspectionCreate,
  InspectionListResponse,
  Photograph,
  PhotographCreate,
  PhotographResponse,
  ReportGenerateResponse,
  SignInUrlResponse,
  TokenVerifyResponse,
} from '../types'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const REQUEST_TIMEOUT_MS = 30000

interface ApiClientOptions {
  token?: string | null
  guestSessionToken?: string | null
}

function buildHeaders(options: ApiClientOptions = {}): HeadersInit {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  }

  if (options.token) {
    ;(headers as Record<string, string>)['Authorization'] = `Bearer ${options.token}`
  }

  if (options.guestSessionToken) {
    ;(headers as Record<string, string>)['X-Guest-Session-Token'] = options.guestSessionToken
  }

  return headers
}

async function parseResponse<T>(response: Response): Promise<T> {
  let body: unknown
  const contentType = response.headers.get('content-type') ?? ''
  if (contentType.includes('application/json')) {
    body = await response.json()
  } else {
    body = await response.text()
  }

  if (!response.ok) {
    const errorBody = body as ApiErrorBody | undefined
    throw new ApiError(
      errorBody?.message || `Request failed with status ${response.status}`,
      response.status,
      errorBody?.error || 'api_error',
      errorBody?.retryable ?? false,
      errorBody?.action,
      errorBody?.details,
    )
  }

  return body as T
}

function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  let timeoutId: ReturnType<typeof setTimeout>
  const timeoutPromise = new Promise<never>((_resolve, reject) => {
    timeoutId = setTimeout(() => reject(new ApiError('Request timed out', 504, 'timeout', true, 'Retry the request')), ms)
  })
  return Promise.race([promise, timeoutPromise]).finally(() => {
    if (timeoutId) clearTimeout(timeoutId)
  })
}

export class ApiClient {
  private baseUrl: string
  private token: string | null = null
  private guestSessionToken: string | null = null

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl.replace(/\/$/, '')
  }

  setToken(token: string | null): void {
    this.token = token
  }

  setGuestSessionToken(token: string | null): void {
    this.guestSessionToken = token
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
    options: ApiClientOptions = {},
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`
    const headers = buildHeaders({
      token: options.token ?? this.token,
      guestSessionToken: options.guestSessionToken ?? this.guestSessionToken,
    })

    const init: RequestInit = {
      method,
      headers,
      ...(body ? { body: JSON.stringify(body) } : {}),
    }

    const response = await fetch(url, init)
    return withTimeout(parseResponse<T>(response), REQUEST_TIMEOUT_MS)
  }

  get<T>(path: string, options?: ApiClientOptions): Promise<T> {
    return this.request<T>('GET', path, undefined, options)
  }

  post<T>(path: string, body?: unknown, options?: ApiClientOptions): Promise<T> {
    return this.request<T>('POST', path, body, options)
  }

  patch<T>(path: string, body?: unknown, options?: ApiClientOptions): Promise<T> {
    return this.request<T>('PATCH', path, body, options)
  }

  delete<T>(path: string, options?: ApiClientOptions): Promise<T> {
    return this.request<T>('DELETE', path, undefined, options)
  }

  async health(): Promise<HealthResponse> {
    return this.get<HealthResponse>('/live')
  }

  async root(): Promise<{ service: string; version: string; status: string }> {
    return this.get<{ service: string; version: string; status: string }>('/')
  }

  async getSignInUrl(): Promise<SignInUrlResponse> {
    return this.get<SignInUrlResponse>('/auth/sign-in-url')
  }

  async verifyToken(token: string): Promise<TokenVerifyResponse> {
    return this.post<TokenVerifyResponse>('/auth/verify', undefined, { token })
  }

  async createGuestSession(): Promise<GuestSessionCreateResponse> {
    return this.post<GuestSessionCreateResponse>('/guest/session')
  }

  async validateGuestSession(guestSessionToken: string): Promise<GuestSessionValidateResponse> {
    return this.get<GuestSessionValidateResponse>('/guest/session/validate', {
      guestSessionToken,
    })
  }

  async consumeGuestAnalysis(guestSessionToken: string): Promise<GuestAnalysisConsumeResponse> {
    return this.post<GuestAnalysisConsumeResponse>(
      '/guest/session/consume-analysis',
      undefined,
      { guestSessionToken },
    )
  }

  async createInspection(payload: InspectionCreate): Promise<Inspection> {
    return this.post<Inspection>('/inspections', payload)
  }

  async listInspections(params?: {
    search?: string
    status?: string
    structure_type?: string
    limit?: number
    offset?: number
  }): Promise<InspectionListResponse> {
    const searchParams = new URLSearchParams()
    if (params?.search) searchParams.set('search', params.search)
    if (params?.status) searchParams.set('status', params.status)
    if (params?.structure_type) searchParams.set('structure_type', params.structure_type)
    if (params?.limit !== undefined) searchParams.set('limit', String(params.limit))
    if (params?.offset !== undefined) searchParams.set('offset', String(params.offset))

    const query = searchParams.toString() ? `?${searchParams.toString()}` : ''
    return this.get<InspectionListResponse>(`/inspections${query}`)
  }

  async getInspection(id: string): Promise<Inspection> {
    return this.get<Inspection>(`/inspections/${id}`)
  }

  async updateInspection(id: string, payload: Partial<InspectionCreate>): Promise<Inspection> {
    return this.patch<Inspection>(`/inspections/${id}`, payload)
  }

  async completeInspection(id: string): Promise<Inspection> {
    return this.post<Inspection>(`/inspections/${id}/complete`)
  }

  async deleteInspection(id: string): Promise<void> {
    return this.delete<void>(`/inspections/${id}`)
  }

  async addPhotograph(inspectionId: string, payload: PhotographCreate): Promise<Photograph> {
    return this.post<Photograph>(`/photos/${inspectionId}`, payload)
  }

  async getPhotograph(photoId: string): Promise<PhotographResponse> {
    return this.get<PhotographResponse>(`/photos/${photoId}`)
  }

  async updatePhotograph(photoId: string, payload: Partial<PhotographCreate>): Promise<PhotographResponse> {
    return this.patch<PhotographResponse>(`/photos/${photoId}`, payload)
  }

  async deletePhotograph(photoId: string): Promise<void> {
    return this.delete<void>(`/photos/${photoId}`)
  }

  async analysePhotograph(photoId: string): Promise<AnalysisResponse> {
    return this.post<AnalysisResponse>(`/photos/${photoId}/analyse`)
  }

  async reanalysePhotograph(photoId: string): Promise<{ photograph_id: string; version_number: number; model_version: string }> {
    return this.post<{ photograph_id: string; version_number: number; model_version: string }>(`/photos/${photoId}/reanalyse`)
  }

  async generateReport(inspectionId: string): Promise<ReportGenerateResponse> {
    return this.post<ReportGenerateResponse>(`/reports/generate/${inspectionId}`)
  }
}

export const apiClient = new ApiClient()
