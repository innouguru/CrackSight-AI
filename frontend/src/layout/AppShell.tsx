import {
  BarChart3,
  ChevronDown,
  ClipboardList,
  FileText,
  LogOut,
  Menu,
  Plus,
  X,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { Brand } from '../components/Brand'
import { SafetyNotice } from '../components/Ui'
import { useAuth } from '../hooks/useAuth'

const navigation = [
  { label: 'Overview', to: '/app', icon: BarChart3, end: true },
  { label: 'Inspections', to: '/app/history', icon: ClipboardList, end: false },
  { label: 'Reports', to: '/app/reports', icon: FileText, end: false },
]

export function AppShell() {
  const { user, isAuthenticated, isLoading, signOut } = useAuth()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [isMobile, setIsMobile] = useState(false)
  const location = useLocation()
  const currentLabel =
    navigation.find((item) =>
      item.end ? location.pathname === item.to : location.pathname.startsWith(item.to),
    )?.label ?? (location.pathname.includes('/new') ? 'New inspection' : 'Inspection details')

  const userName = user.user_id ? (user.email ? user.email.split('@')[0] : 'User') : 'Inspector'
  const userInitials = user.user_id
    ? user.user_id
        .split('')
        .filter((ch) => /[A-Z]/.test(ch))
        .slice(0, 2)
        .join('') || 'U'
    : 'UI'

  useEffect(() => {
    const mediaQuery = window.matchMedia('(max-width: 760px)')
    const updateViewport = () => {
      setIsMobile(mediaQuery.matches)
      if (!mediaQuery.matches) setMobileOpen(false)
    }
    updateViewport()
    mediaQuery.addEventListener('change', updateViewport)
    return () => mediaQuery.removeEventListener('change', updateViewport)
  }, [])

  if (isLoading) {
    return (
      <div className="app-frame" style={{ display: 'flex', height: '100vh' }}>
        <div className="app-main" style={{ flex: 1 }}>
          <div className="app-content" style={{ padding: 40 }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '60vh', textAlign: 'center' }}>
              <div style={{ width: 40, height: 40, border: '3px solid #e6ebe9', borderTopColor: '#167f78', borderRadius: '50%', animation: 'spin 0.8s linear infinite', marginBottom: 12 }} />
              <p style={{ color: '#718087', fontSize: 12 }}>Resolving session…</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="app-frame">
      {mobileOpen && (
        <button
          className="sidebar-backdrop"
          onClick={() => setMobileOpen(false)}
          aria-label="Close navigation"
        />
      )}
      <aside
        className={`sidebar${mobileOpen ? ' sidebar--open' : ''}`}
        aria-hidden={isMobile && !mobileOpen}
        inert={isMobile && !mobileOpen}
      >
        <div className="sidebar__brand-row">
          <Brand />
          <button
            className="icon-button sidebar__close"
            onClick={() => setMobileOpen(false)}
            aria-label="Close navigation"
          >
            <X size={19} />
          </button>
        </div>
        <div className="workspace-switcher">
          <span className="workspace-switcher__avatar">{userInitials}</span>
          <span className="workspace-switcher__text">
            <strong>{isAuthenticated ? 'Your Workspace' : 'Workspace'}</strong>
            <small>{isAuthenticated ? 'Signed in' : 'Guest access'}</small>
          </span>
          <ChevronDown size={15} />
        </div>
        <p className="sidebar__label">WORKSPACE</p>
        <nav className="sidebar-nav" aria-label="Main navigation">
          {navigation.map(({ label, to, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) => `sidebar-nav__link${isActive ? ' is-active' : ''}`}
            >
              <Icon size={18} strokeWidth={1.8} />
              <span>{label}</span>
              {label === 'Inspections' && <span className="nav-count">0</span>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar__bottom">
          <NavLink to="/app/inspections/new" className="sidebar-cta" onClick={() => setMobileOpen(false)}>
            <Plus size={17} /> New inspection
          </NavLink>
          <div className="account-row">
            <div className="account-avatar">{userInitials}</div>
            <span className="account-row__text">
              <strong>{userName}</strong>
              <small>{isAuthenticated ? 'Inspector' : 'Guest'}</small>
            </span>
            {isAuthenticated && (
              <button
                className="icon-button account-row__menu"
                onClick={() => void signOut()}
                aria-label="Sign out"
              >
                <LogOut size={16} />
              </button>
            )}
          </div>
        </div>
      </aside>

      <div className="app-main">
        <header className="topbar">
          <div className="topbar__left">
            <button
              className="icon-button topbar__menu"
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation"
            >
              <Menu size={20} />
            </button>
            <div className="breadcrumbs">
              <span>Workspace</span><span className="breadcrumbs__slash">/</span><strong>{currentLabel}</strong>
            </div>
          </div>
          <div className="topbar__right">
            <span className="prototype-chip"><span /> {isAuthenticated ? 'Authenticated' : 'Guest session'}</span>
            <button className="topbar__avatar" aria-label={userName} onClick={() => void signOut()}>
              {userInitials}
            </button>
          </div>
        </header>
        <main className="app-content">
          <Outlet />
          <footer className="workspace-footer">
            <SafetyNotice compact />
            <span>
              CrackSight AI · {isAuthenticated ? 'Signed-in workspace' : 'Guest session'} ·
              <Link to="/app/access-denied">Access-state example</Link>
            </span>
          </footer>
        </main>
      </div>
    </div>
  )
}
