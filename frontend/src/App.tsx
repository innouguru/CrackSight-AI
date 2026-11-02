import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { PrototypeProvider } from './data/PrototypeContext'
import { AppShell } from './layout/AppShell'
import { AuthPage } from './pages/AuthPage'
import { AccessDeniedPage } from './pages/AccessDeniedPage'
import { DashboardPage } from './pages/DashboardPage'
import { GuestAnalysisPage } from './pages/GuestAnalysisPage'
import { HistoryPage } from './pages/HistoryPage'
import { InspectionDetailPage } from './pages/InspectionDetailPage'
import { LandingPage } from './pages/LandingPage'
import { NewInspectionPage } from './pages/NewInspectionPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { ReportsPage } from './pages/ReportsPage'
import { ResultsPage } from './pages/ResultsPage'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <PrototypeProvider>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/sign-in" element={<AuthPage mode="sign-in" />} />
          <Route path="/sign-up" element={<AuthPage mode="sign-up" />} />
          <Route path="/try" element={<GuestAnalysisPage />} />
          <Route path="/try/results" element={<ResultsPage />} />
          <Route path="/app" element={<AppShell />}>
            <Route index element={<DashboardPage />} />
            <Route path="history" element={<HistoryPage />} />
            <Route path="inspections/new" element={<NewInspectionPage />} />
            <Route path="inspections/:inspectionId" element={<InspectionDetailPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="access-denied" element={<AccessDeniedPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </PrototypeProvider>
    </BrowserRouter>
  )
}

export default App
