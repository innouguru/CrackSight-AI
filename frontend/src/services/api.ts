import { ApiError } from '../types'
import type {
  AnalysisResponse,
  ApiErrorBody,
  GuestAnalysisConsumeResponse,
  GuestPhotographUploadResponse,
  GuestSessionCreateResponse,
  GuestSessionValidateResponse,
  HealthResponse,
  Inspection,
  InspectionCreate,
  InspectionListResponse,
  Photograph,
  PhotographCreate,
  PhotographListResponse,
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

  /**
   * Upload a photograph for a guest session using multipart/form-data.
   */
  async uploadGuestPhotograph(
    file: File,
    structureType: string,
    options: ApiClientOptions = {},
  ): Promise<GuestPhotographUploadResponse> {
    const url = `${this.baseUrl}/guest/session/photograph`
    const formData = new FormData()
    formData.append('file', file)
    formData.append('structure_type', structureType)

    const headers: HeadersInit = {}
    if (options.guestSessionToken) {
      headers['X-Guest-Session-Token'] = options.guestSessionToken
    }
    if (this.guestSessionToken) {
      headers['X-Guest-Session-Token'] = this.guestSessionToken
    }

    const init: RequestInit = {
      method: 'POST',
      headers,
      body: formData,
    }

    const response = await fetch(url, init)
    return withTimeout(parseResponse<GuestPhotographUploadResponse>(response), REQUEST_TIMEOUT_MS)
  }

  /**
   * Download a guest result file (original, mask, or overlay).
   * Returns a blob URL that can be used as an image src or download link.
   */
  async downloadGuestResult(
    photographId: string,
    fileType: 'original' | 'mask' | 'overlay',
    options: ApiClientOptions = {},
  ): Promise<string> {
    const url = `${this.baseUrl}/guest/session/photograph/${photographId}/${fileType}`

    const headers: HeadersInit = {}
    if (options.guestSessionToken) {
      headers['X-Guest-Session-Token'] = options.guestSessionToken
    }
    if (this.guestSessionToken) {
      headers['X-Guest-Session-Token'] = this.guestSessionToken
    }

    const init: RequestInit = {
      method: 'GET',
      headers,
    }

    const response = await fetch(url, init)

    if (!response.ok) {
      const errorBody = await response
        .json()
        .catch(() => ({ message: `Request failed with status ${response.status}` }))
      throw new ApiError(
        errorBody?.message || `Request failed with status ${response.status}`,
        response.status,
        errorBody?.error || 'api_error',
        errorBody?.retryable ?? false,
        errorBody?.action,
        errorBody?.details,
      )
    }

    const blob = await response.blob()
    return URL.createObjectURL(blob)
  }

  async createInspection(payload: InspectionCreate): Promise<Inspection> {
    return this.post<Inspection>('/inspections', payload)
  }

  async listInspections(params?: {
    search?: string
    status?: string
    structure_type?: string
    verification_status?: string
    date_from?: string
    date_to?: string
    limit?: number
    offset?: number
  }): Promise<InspectionListResponse> {
    const searchParams = new URLSearchParams()
    if (params?.search) searchParams.set('search', params.search)
    if (params?.status) searchParams.set('status', params.status)
    if (params?.structure_type) searchParams.set('structure_type', params.structure_type)
    if (params?.verification_status) searchParams.set('verification_status', params.verification_status)
    if (params?.date_from) searchParams.set('date_from', params.date_from)
    if (params?.date_to) searchParams.set('date_to', params.date_to)
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

  async listInspectionPhotographs(
    inspectionId: string,
  ): Promise<PhotographListResponse> {
    return this.get<PhotographListResponse>(
      `/inspections/${inspectionId}/photos`
    )
  }

  /**
   * Upload a photograph to an owned draft inspection using multipart/form-data.
   * The backend stores the original image in private object storage and persists the
   * photograph record associated with the authenticated user, the inspection,
   * and the selected structure type.
   */
  async uploadPhotograph(
    inspectionId: string,
    file: File,
    structureType: string,
  ): Promise<Photograph> {
    const url = `${this.baseUrl}/photos/${inspectionId}/upload`
    const formData = new FormData()
    formData.append('file', file)
    formData.append('structure_type', structureType)

    const headers: HeadersInit = {}
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`
    }

    const init: RequestInit = {
      method: 'POST',
      headers,
      body: formData,
    }

    const response = await fetch(url, init)
    return withTimeout(parseResponse<Photograph>(response), REQUEST_TIMEOUT_MS)
  }

  /**
   * Download a photograph image (original, mask, or overlay) from private
   * storage and return a blob URL usable as an image src or download link.
   */
  async downloadPhotographImage(
    photoId: string,
    imageType: 'original' | 'mask' | 'overlay' = 'original',
  ): Promise<string> {
    const url = `${this.baseUrl}/photos/${photoId}/download/${imageType}`

    const headers: HeadersInit = {}
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`
    }

    const init: RequestInit = {
      method: 'GET',
      headers,
    }

    const response = await fetch(url, init)

    if (!response.ok) {
      const errorBody = await response
        .json()
        .catch(() => ({ message: `Request failed with status ${response.status}` }))
      throw new ApiError(
        errorBody?.message || `Request failed with status ${response.status}`,
        response.status,
        errorBody?.error || 'api_error',
        errorBody?.retryable ?? false,
        errorBody?.action,
        errorBody?.details,
      )
    }

    const blob = await response.blob()
    return URL.createObjectURL(blob)
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

  /**
   * Download a generated PDF inspection report from private storage and
   * return a blob URL. The caller is responsible for revoking it.
   */
  async downloadReportPdf(reportId: string): Promise<string> {
    const url = `${this.baseUrl}/reports/${reportId}/download`

    const headers: HeadersInit = {}
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`
    }

    const init: RequestInit = {
      method: 'GET',
      headers,
    }

    const response = await fetch(url, init)

    if (!response.ok) {
      const contentType = response.headers.get('content-type') ?? ''
      const errorBody = contentType.includes('application/json')
        ? await response.json().catch(() => null)
        : null
      throw new ApiError(
        errorBody?.message || `Request failed with status ${response.status}`,
        response.status,
        errorBody?.error || 'api_error',
        errorBody?.retryable ?? false,
        errorBody?.action,
        errorBody?.details,
      )
    }

    const blob = await response.blob()
    return URL.createObjectURL(blob)
  }
}

export const apiClient = new ApiClient()
