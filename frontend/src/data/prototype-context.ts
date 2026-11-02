import { createContext } from 'react'
import type { Inspection, InspectionStatus } from './mockData'

type NewInspectionInput = Pick<Inspection, 'title' | 'location' | 'buildingType' | 'structure'> & {
  notes?: string
}

export interface PrototypeContextValue {
  inspections: Inspection[]
  guestAnalysesRemaining: number
  createInspection: (input: NewInspectionInput) => Inspection
  updateInspectionStatus: (id: string, status: InspectionStatus) => void
  addSamplePhotograph: (id: string) => void
  consumeGuestAnalysis: () => boolean
}

export const PrototypeContext = createContext<PrototypeContextValue | null>(null)
