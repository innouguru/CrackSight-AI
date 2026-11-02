import { useMemo, useState, type ReactNode } from 'react'
import { PrototypeContext, type PrototypeContextValue } from './prototype-context'
import { initialInspections, type Inspection } from './mockData'

export function PrototypeProvider({ children }: { children: ReactNode }) {
  const [inspections, setInspections] = useState(initialInspections)
  const [guestAnalysesUsed, setGuestAnalysesUsed] = useState(0)

  const value = useMemo<PrototypeContextValue>(
    () => ({
      inspections,
      guestAnalysesRemaining: Math.max(0, 3 - guestAnalysesUsed),
      createInspection: (input) => {
        const inspection: Inspection = {
          ...input,
          id: `CS-${String(249 + inspections.length - initialInspections.length).padStart(4, '0')}`,
          date: new Intl.DateTimeFormat('en-GB', {
            day: '2-digit',
            month: 'short',
            year: 'numeric',
          }).format(new Date()),
          status: 'Draft',
          photoCount: 0,
          verification: 'Not verified',
        }
        setInspections((current) => [inspection, ...current])
        return inspection
      },
      updateInspectionStatus: (id, status) => {
        setInspections((current) =>
          current.map((inspection) =>
            inspection.id === id ? { ...inspection, status } : inspection,
          ),
        )
      },
      addSamplePhotograph: (id) => {
        setInspections((current) =>
          current.map((inspection) =>
            inspection.id === id
              ? { ...inspection, photoCount: inspection.photoCount + 1 }
              : inspection,
          ),
        )
      },
      consumeGuestAnalysis: () => {
        if (guestAnalysesUsed >= 3) {
          return false
        }
        setGuestAnalysesUsed((used) => used + 1)
        return true
      },
    }),
    [guestAnalysesUsed, inspections],
  )

  return <PrototypeContext.Provider value={value}>{children}</PrototypeContext.Provider>
}
