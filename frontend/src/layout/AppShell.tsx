import {
  BarChart3,
  ChevronDown,
  ClipboardList,
  FileText,
  Menu,
  Plus,
  X,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { Brand } from '../components/Brand'
import { SafetyNotice } from '../components/Ui'

const navigation = [
  { label: 'Overview', to: '/app', icon: BarChart3, end: true },
  { label: 'Inspections', to: '/app/history', icon: ClipboardList, end: false },
  { label: 'Reports', to: '/app/reports', icon: FileText, end: false },
]

export function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [isMobile, setIsMobile] = useState(false)
  const location = useLocation()
  const currentLabel =
    navigation.find((item) =>
      item.end ? location.pathname === item.to : location.pathname.startsWith(item.to),
    )?.label ?? (location.pathname.includes('/new') ? 'New inspection' : 'Inspection details')

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
          <span className="workspace-switcher__avatar">R</span>
          <span className="workspace-switcher__text">
            <strong>Riverside Survey</strong>
            <small>Personal workspace</small>
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
              {label === 'Inspections' && <span className="nav-count">12</span>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar__bottom">
          <div className="allowance-card">
            <div className="allowance-card__top">
              <span>Monthly analyses</span>
              <span className="allowance-card__count">18 / 100</span>
            </div>
            <div className="progress-track"><span style={{ width: '18%' }} /></div>
            <p>Resets 1 Dec</p>
          </div>
          <NavLink to="/app/inspections/new" className="sidebar-cta" onClick={() => setMobileOpen(false)}>
            <Plus size={17} /> New inspection
          </NavLink>
          <div className="account-row">
            <div className="account-avatar">JM</div>
            <span className="account-row__text">
              <strong>Jordan Miller</strong>
              <small>Inspector</small>
            </span>
            <button className="icon-button account-row__menu" aria-label="Account options">
              <ChevronDown size={16} />
            </button>
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
            <span className="prototype-chip"><span /> Prototype workspace</span>
            <button className="topbar__avatar" aria-label="Jordan Miller account">JM</button>
          </div>
        </header>
        <main className="app-content">
          <Outlet />
          <footer className="workspace-footer">
            <SafetyNotice compact />
            <span>CrackSight AI · Prototype data · <Link to="/app/access-denied">Access-state example</Link></span>
          </footer>
        </main>
      </div>
    </div>
  )
}
