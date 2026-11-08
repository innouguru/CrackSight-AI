import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ReportsPage } from './ReportsPage'
import { apiClient } from '../services/api'

// The backend provides generation + individual download only (no report
// listing), so this page intentionally renders sample content with honest
// copy; the real generation flow lives on the inspection detail page.
vi.mock('../services/api', () => ({
  apiClient: {
    generateReport: vi.fn(),
    downloadReportPdf: vi.fn(),
  },
}))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => mockNavigate }
})

describe('ReportsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  function TestWrapper() {
    return (
      <MemoryRouter initialEntries={['/app/reports']}>
        <ReportsPage />
      </MemoryRouter>
    )
  }

  it('renders the sample preview with honest demo messaging', () => {
    render(TestWrapper())

    expect(screen.getByText('PDF reports')).toBeTruthy()
    expect(screen.getAllByText(/Report records and the preview below are sample content/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/Real PDF reports are generated and downloaded per inspection/i)).toBeTruthy()
    expect(screen.getByText('Recent reports')).toBeTruthy()
  })

  it('navigates to inspection history from the generate action (no fake generation call)', () => {
    const mockGenerateReport = vi.mocked(apiClient.generateReport)
    render(TestWrapper())

    fireEvent.click(screen.getByRole('button', { name: /Generate report/i }))

    expect(mockNavigate).toHaveBeenCalledWith('/app/history')
    expect(mockGenerateReport).not.toHaveBeenCalled()
  })

  it('download guidance stays a sample interaction and calls no backend', () => {
    const mockDownloadReport = vi.mocked(apiClient.downloadReportPdf)
    render(TestWrapper())

    fireEvent.click(screen.getByRole('button', { name: /Download PDF/i }))

    expect(screen.getAllByText(/not backed by a report-history API/i).length).toBeGreaterThan(0)
    expect(mockDownloadReport).not.toHaveBeenCalled()
  })
})
