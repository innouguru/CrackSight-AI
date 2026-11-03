import { BrowserRouter, Route, Routes, Navigate, useLocation } from 'react-router-dom'
import { AppShell } from './layout/AppShell'
import { LandingPage } from './pages/LandingPage'
import { AuthPage } from './pages/AuthPage'
import { AccessDeniedPage } from './pages/AccessDeniedPage'
import { DashboardPage } from './pages/DashboardPage'
import { GuestAnalysisPage } from './pages/GuestAnalysisPage'
import { HistoryPage } from './pages/HistoryPage'
import { InspectionDetailPage } from './pages/InspectionDetailPage'
import { NewInspectionPage } from './pages/NewInspectionPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { ReportsPage } from './pages/ReportsPage'
import { ResultsPage } from './pages/ResultsPage'
import { PublicLayout } from './layouts/PublicLayout'
import { GuestLayout } from './layouts/GuestLayout'
import { useAuth } from './hooks/useAuth'
import { LoadingState } from './components/LoadingState'
import './App.css'

function RequireAuth() {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return <LoadingState message="Resolving session…" />
  }

  if (!isAuthenticated) {
    return <Navigate to="/sign-in" replace state={{ from: location.pathname }} />
  }

  return null
}

function RequireNoAuth() {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return <LoadingState message="Resolving session…" />
  }

  if (isAuthenticated) {
    return <Navigate to="/app" replace state={{ from: location.pathname }} />
  }

  return null
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<PublicLayout />}>
          <Route path="/" element={<LandingPage />} />
          <Route
            path="/sign-in"
            element={
              <>
                <RequireNoAuth />
                <AuthPage mode="sign-in" />
              </>
            }
          />
          <Route
            path="/sign-up"
            element={
              <>
                <RequireNoAuth />
                <AuthPage mode="sign-up" />
              </>
            }
          />
        </Route>

        <Route
          path="/try"
          element={
            <>
              <GuestLayout />
            </>
          }
        >
          <Route index element={<GuestAnalysisPage />} />
          <Route path="results" element={<ResultsPage />} />
        </Route>

        <Route
          path="/app"
          element={
            <>
              <RequireAuth />
              <AppShell />
            </>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="inspections/new" element={<NewInspectionPage />} />
          <Route path="inspections/:inspectionId" element={<InspectionDetailPage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="access-denied" element={<AccessDeniedPage />} />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
