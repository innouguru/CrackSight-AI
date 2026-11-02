export type InspectionStatus = 'Draft' | 'Completed'
export type StructureType = 'Wall' | 'Beam' | 'Column'
export type VerificationStatus =
  | 'Not verified'
  | 'Correct detection'
  | 'Partially correct'
  | 'Incorrect detection'

export interface Inspection {
  id: string
  title: string
  location: string
  buildingType: string
  date: string
  status: InspectionStatus
  structure: StructureType
  photoCount: number
  verification: VerificationStatus
  notes?: string
}

export const demoImages = {
  original: '/demo/crack-wall.jpg',
  overlay: '/demo/crack-overlay.png',
  mask: '/demo/crack-mask.png',
  probability: '/demo/crack-probability.png',
}

export const initialInspections: Inspection[] = [
  {
    id: 'CS-0248',
    title: 'North elevation — level 2',
    location: 'Riverside House, Bristol',
    buildingType: 'Residential',
    date: '02 Nov 2026',
    status: 'Draft',
    structure: 'Wall',
    photoCount: 4,
    verification: 'Not verified',
  },
  {
    id: 'CS-0247',
    title: 'Loading bay columns',
    location: 'Westgate Works, Bristol',
    buildingType: 'Industrial',
    date: '31 Oct 2026',
    status: 'Completed',
    structure: 'Column',
    photoCount: 8,
    verification: 'Correct detection',
  },
  {
    id: 'CS-0246',
    title: 'Plant room beam review',
    location: 'Harbour Point, Bath',
    buildingType: 'Commercial',
    date: '29 Oct 2026',
    status: 'Completed',
    structure: 'Beam',
    photoCount: 3,
    verification: 'Partially correct',
  },
  {
    id: 'CS-0245',
    title: 'Ground floor partition',
    location: 'Riverside House, Bristol',
    buildingType: 'Residential',
    date: '27 Oct 2026',
    status: 'Draft',
    structure: 'Wall',
    photoCount: 2,
    verification: 'Not verified',
  },
]

export const reportRecords = [
  { id: 'RPT-0182', inspection: 'Loading bay columns', date: '31 Oct 2026', pages: 9 },
  { id: 'RPT-0181', inspection: 'Plant room beam review', date: '29 Oct 2026', pages: 5 },
  { id: 'RPT-0179', inspection: 'South stairwell survey', date: '24 Oct 2026', pages: 7 },
]

export const structureTypes: StructureType[] = ['Wall', 'Beam', 'Column']
