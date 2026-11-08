import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { InspectionDetailPage } from './InspectionDetailPage'
import { useAuth } from '../hooks/useAuth'
import { apiClient } from '../services/api'
import { ApiError, type Inspection, type PhotographMetadataResponse } from '../types'

vi.mock('../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}))

vi.mock('../services/api', () => ({
  apiClient: {
    setToken: vi.fn(),
    getInspection: vi.fn(),
    listInspectionPhotographs: vi.fn(),
    uploadPhotograph: vi.fn(),
    downloadPhotographImage: vi.fn(),
    generateReport: vi.fn(),
    downloadReportPdf: vi.fn(),
  },
}))

const mockUseAuth = vi.mocked(useAuth)
const mockGetInspection = vi.mocked(apiClient.getInspection)
const mockListPhotographs = vi.mocked(apiClient.listInspectionPhotographs)
const mockGenerateReport = vi.mocked(apiClient.generateReport)
const mockDownloadReport = vi.mocked(apiClient.downloadReportPdf)

const inspectionId = '11111111-2222-4333-8444-555555555555'
const reportId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'

const mockInspection: Inspection = {
  id: inspectionId,
  user_id: 'clerk_user_123',
  title: 'North elevation — level 2',
  building_type: 'Residential',
  building_location: 'Riverside House, Bristol',
  notes: 'Hairline crack above window',
  status: 'draft',
  created_at: '2026-11-02T12:00:00+00:00',
  completed_at: null,
  photograph_count: 1,
}

const mockPhoto: PhotographMetadataResponse = {
  id: '00000000-0000-4000-8000-000000000010',
  inspection_id: inspectionId,
  structure_type: 'wall',
  observation: null,
  verification_status: 'not_verified',
  model_version: null,
  prediction_timestamp: null,
  pixel_measurements: null,
  created_at: '2026-11-02T12:05:00+00:00',
  prediction_available: false,
}

function mockAuthenticatedAuth() {
  mockUseAuth.mockReturnValue({
    isAuthenticated: true,
    isGuest: false,
    isLoading: false,
    user: { user_id: 'clerk_user_123', email: 'alice@example.com', is_guest: false, is_authenticated: true, guest_session_id: null },
    signIn: vi.fn(),
    signUp: vi.fn(),
    signInWithGoogle: vi.fn(),
    signOut: vi.fn(),
    getToken: async () => 'clerk-token',
  })
}

function TestWrapper() {
  return (
    <MemoryRouter initialEntries={[`/app/inspections/${inspectionId}`]}>
      <Routes>
        <Route path="/app/inspections/:inspectionId" element={<InspectionDetailPage />} />
      </Routes>
    </MemoryRouter>
  )
}

async function renderLoadedPage(status: 'draft' | 'completed' = 'draft') {
  mockGetInspection.mockResolvedValue({ ...mockInspection, status })
  mockListPhotographs.mockResolvedValue({
    inspection_id: inspectionId,
    photographs: [mockPhoto],
    total: 1,
  })
  render(TestWrapper())
  await waitFor(() => {
    expect(screen.getByText('North elevation — level 2')).toBeTruthy()
  })
}

describe('InspectionDetailPage (report integration)', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    const originalCreate = URL.createObjectURL
    URL.createObjectURL = vi.fn(() => 'blob:mock-url') as typeof URL.createObjectURL
    URL.revokeObjectURL = vi.fn() as typeof URL.revokeObjectURL
    mockAuthenticatedAuth()
    ;(URL as unknown as { _originalCreate?: typeof URL.createObjectURL })._originalCreate = originalCreate
  })

  afterEach(() => {
    const original = (URL as unknown as { _originalCreate?: typeof URL.createObjectURL })._originalCreate
    if (original) {
      URL.createObjectURL = original
    }
    vi.restoreAllMocks()
  })

  // ---- existing functionality stays intact ----

  it('renders inspection details and photographs on load', async () => {
    await renderLoadedPage()

    expect(mockGetInspection).toHaveBeenCalledWith(inspectionId)
    expect(mockListPhotographs).toHaveBeenCalledWith(inspectionId)
    expect(screen.getAllByText('Wall').length).toBeGreaterThan(0)
    expect(screen.getByText('Download original')).toBeTruthy()
    expect(screen.getByRole('button', { name: /Upload photograph/i })).toBeTruthy()
  })

  it('does not show report actions for unauthenticated users', async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isGuest: true,
      isLoading: false,
      user: { user_id: null, email: null, is_guest: true, is_authenticated: false, guest_session_id: 'guest-1' },
      signIn: vi.fn(),
      signUp: vi.fn(),
      signInWithGoogle: vi.fn(),
      signOut: vi.fn(),
      getToken: async () => null,
    })
    await renderLoadedPage()

    expect(screen.queryByRole('button', { name: /Generate report/i })).toBeNull()
    expect(screen.queryByText('PDF report')).toBeNull()
    expect(mockGenerateReport).not.toHaveBeenCalled()
  })

  it('shows report actions for completed inspections as well', async () => {
    await renderLoadedPage('completed')

    expect(screen.getByRole('button', { name: /Generate report/i })).toBeTruthy()
  })

  // ---- generation ----

  it('generates a report and shows the returned report ID once', async () => {
    mockGenerateReport.mockResolvedValue({
      report_id: reportId,
      generated_at: '2026-11-08T12:00:00+00:00',
      download_url: `/reports/${reportId}/download`,
    })
    await renderLoadedPage()

    const button = screen.getByRole('button', { name: /Generate report/i })
    fireEvent.click(button)
    fireEvent.click(button) // second click while generating must be ignored

    await waitFor(() => {
      expect(mockGenerateReport).toHaveBeenCalledTimes(1)
    })
    await waitFor(() => {
      expect(screen.getByText(new RegExp(reportId))).toBeTruthy()
    })
  })

  it('shows an error on generation failure and allows retry', async () => {
    mockGenerateReport
      .mockRejectedValueOnce(new ApiError('PDF generation failed', 500, 'server_error', false))
      .mockResolvedValueOnce({
        report_id: reportId,
        generated_at: '2026-11-08T12:00:00+00:00',
        download_url: `/reports/${reportId}/download`,
      })
    await renderLoadedPage()

    fireEvent.click(screen.getByRole('button', { name: /Generate report/i }))
    await waitFor(() => {
      expect(screen.getByText('PDF generation failed')).toBeTruthy()
    })
    expect(screen.queryByText(new RegExp(reportId))).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: /Generate report/i }))
    await waitFor(() => {
      expect(mockGenerateReport).toHaveBeenCalledTimes(2)
      expect(screen.getByText(new RegExp(reportId))).toBeTruthy()
    })
  })

  // ---- download ----

  it('downloads the generated PDF using the backend report ID and a sensible filename', async () => {
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const createdAnchors: HTMLAnchorElement[] = []
    const originalCreateElement = Object.getOwnPropertyDescriptor(
      Document.prototype,
      'createElement',
    )!.value
    vi.spyOn(Document.prototype, 'createElement').mockImplementation(((tag: string) => {
      const el = originalCreateElement.call(document, tag as keyof HTMLElementTagNameMap)
      createdAnchors.push(el as HTMLAnchorElement)
      return el
    }) as any)
    mockGenerateReport.mockResolvedValue({
      report_id: reportId,
      generated_at: '2026-11-08T12:00:00+00:00',
      download_url: `/reports/${reportId}/download`,
    })
    mockDownloadReport.mockResolvedValue('blob:pdf-url')
    await renderLoadedPage()

    fireEvent.click(screen.getByRole('button', { name: /Generate report/i }))
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Download PDF report/i })).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: /Download PDF report/i }))
    await waitFor(() => {
      expect(mockDownloadReport).toHaveBeenCalledTimes(1)
      expect(mockDownloadReport).toHaveBeenCalledWith(reportId)
      expect(clickSpy).toHaveBeenCalled()
    })
    // The anchor used for the download carries the backend-consistent filename
    const anchor = createdAnchors.find((a) => a.getAttribute('href') === 'blob:pdf-url')
    expect(anchor).toBeDefined()
    expect(anchor!.download).toBe(`cracksight-report-${reportId}.pdf`)
  })

  it('shows an error when the PDF download fails', async () => {
    mockGenerateReport.mockResolvedValue({
      report_id: reportId,
      generated_at: '2026-11-08T12:00:00+00:00',
      download_url: `/reports/${reportId}/download`,
    })
    mockDownloadReport.mockRejectedValue(new ApiError('Report not found', 404, 'not_found', false))
    await renderLoadedPage()

    fireEvent.click(screen.getByRole('button', { name: /Generate report/i }))
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Download PDF report/i })).toBeTruthy()
    })
    fireEvent.click(screen.getByRole('button', { name: /Download PDF report/i }))
    await waitFor(() => {
      expect(screen.getByText('Report not found')).toBeTruthy()
    })
  })
})
