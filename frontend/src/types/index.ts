export type InspectionStatus = 'draft' | 'completed'
export type StructureType = 'wall' | 'beam' | 'column'
export type VerificationStatus = 'not_verified' | 'correct' | 'incorrect' | 'partial'

export interface UserIdentity {
  user_id: string | null
  email: string | null
  is_guest: boolean
  is_authenticated: boolean
  guest_session_id: string | null
}

export interface AuthState {
  user: UserIdentity
  isAuthenticated: boolean
  isGuest: boolean
  isLoading: boolean
  signIn: (emailAddress: string, password: string) => void
  signUp: (emailAddress: string, password: string, firstName?: string) => void
  signInWithGoogle: () => void
  signOut: () => void
  getToken: () => Promise<string | null>
}

export interface HealthResponse {
  status: string
  service: string
  version: string
}

export interface SignInUrlResponse {
  sign_in_url: string
}

export interface TokenVerifyResponse {
  valid: boolean
  user_id: string | null
  email: string | null
}

export interface Inspection {
  id: string
  user_id: string
  title: string
  building_type: string | null
  building_location: string | null
  notes: string | null
  status: InspectionStatus
  created_at: string
  completed_at: string | null
  photograph_count: number
}

export interface InspectionCreate {
  title: string
  building_type?: string
  building_location?: string
  notes?: string
}

export interface InspectionListResponse {
  inspections: Inspection[]
  total: number
}

/**
 * Backend-mapped inspection view for dashboard/history pages.
 * Maps backend Inspection fields to UI-friendly names.
 * ``structure`` and ``verification`` are optional because they are
 * per-photograph attributes in the backend and are not stored on the
 * inspection record itself.
 */
export interface InspectionView {
  id: string
  title: string
  location: string | null
  buildingType: string | null
  date: string
  status: 'Draft' | 'Completed'
  structure?: string
  photoCount: number
  verification?: string
  notes?: string | null
}

/**
 * Maps a backend ``Inspection`` to an ``InspectionView`` for UI display.
 * Does not fabricate fields that are not present in the backend response
 * (e.g. ``structure`` and ``verification`` are per-photograph attributes
 * and are left undefined at the inspection level).
 */
export function toInspectionView(insp: Inspection): InspectionView {
  return {
    id: insp.id,
    title: insp.title,
    location: insp.building_location,
    buildingType: insp.building_type,
    date: formatInspectionDate(insp.created_at),
    status: insp.status === 'completed' ? 'Completed' : 'Draft',
    photoCount: insp.photograph_count,
    notes: insp.notes,
  }
}

/**
 * Formats an ISO date string from the backend into a short display format
 * (e.g. "02 Nov 2026"), matching the prototype's date style.
 */
export function formatInspectionDate(isoString: string): string {
  return new Date(isoString).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

export interface Photograph {
  id: string
  inspection_id: string
  user_id: string
  structure_type: StructureType
  observation: string | null
  verification_status: VerificationStatus
  original_image_key: string
  prediction_mask_key: string | null
  prediction_overlay_key: string | null
  model_version: string | null
  prediction_timestamp: string | null
  pixel_measurements: Record<string, unknown> | null
  created_at: string
}

export interface PhotographCreate {
  structure_type: StructureType
  original_image_key: string
  observation?: string
}

export interface PhotographResponse {
  id: string
  inspection_id: string
  user_id: string
  structure_type: StructureType
  observation: string | null
  verification_status: VerificationStatus
  original_image_key: string
  prediction_mask_key: string | null
  prediction_overlay_key: string | null
  model_version: string | null
  prediction_timestamp: string | null
  pixel_measurements: Record<string, unknown> | null
  created_at: string
}

export interface PhotographMetadataResponse {
  id: string
  inspection_id: string
  structure_type: StructureType
  observation: string | null
  verification_status: VerificationStatus
  model_version: string | null
  prediction_timestamp: string | null
  pixel_measurements: Record<string, unknown> | null
  created_at: string
  prediction_available: boolean
}

export interface PhotographListResponse {
  inspection_id: string
  photographs: PhotographMetadataResponse[]
  total: number
}

export interface AnalysisResponse {
  photograph_id: string
  prediction_mask_key: string
  prediction_overlay_key: string
  original_image_key: string
  model_version: string
  prediction_timestamp: string
  inference_duration_ms: number
  processing_status: string
  original_image_size: [number, number]
  pixel_measurements: PixelMeasurements | null
  analyses_remaining: number | null
}

export interface PixelMeasurements {
  crack_pixel_count: number
  crack_pixel_percentage: number
  bounding_box: {
    min_x: number
    min_y: number
    max_x: number
    max_y: number
  } | null
  region_count: number
}

export interface GuestSession {
  session_token: string
  session_id: string
  expires_at: string
  max_analyses: number
  analyses_count: number
  analyses_remaining: number
}

export interface GuestSessionCreateResponse {
  session_token: string
  session_id: string
  expires_at: string
  max_analyses: number
  analyses_count: number
}

export interface GuestSessionValidateResponse {
  valid: boolean
  session_id: string | null
  analyses_count: number
  max_analyses: number
  analyses_remaining: number
  expires_at: string | null
}

export interface GuestAnalysisConsumeResponse {
  consumed: boolean
  analyses_count: number
  max_analyses: number
  analyses_remaining: number
}

export interface GuestPhotographUploadResponse {
  photograph_id: string
  session_id: string
  structure_type: string
  original_image_key: string
  file_size: number
  content_type: string
  analyses_remaining: number
}

export interface ReportGenerateResponse {
  report_id: string
  generated_at: string
  download_url: string
}

export interface ApiErrorBody {
  error: string
  message: string
  retryable: boolean
  action?: string
  details?: Record<string, unknown>
}

export class ApiError extends Error {
  status: number
  errorCode: string
  retryable: boolean
  action?: string
  details?: Record<string, unknown>

  constructor(
    message: string,
    status: number,
    errorCode: string,
    retryable: boolean,
    action?: string,
    details?: Record<string, unknown>,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.errorCode = errorCode
    this.retryable = retryable
    this.action = action
    this.details = details
  }
}
