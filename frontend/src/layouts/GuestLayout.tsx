import { Outlet } from 'react-router-dom'
import { Brand } from '../components/Brand'
import { SafetyNotice } from '../components/Ui'

export function GuestLayout() {
  return (
    <div className="guest-layout">
      <header className="guest-layout__header">
        <div className="guest-layout__brand">
          <Brand compact />
        </div>
        <div className="guest-layout__actions">
          <a className="guest-layout__signin" href="/sign-in">
            Sign in
          </a>
        </div>
      </header>
      <main className="guest-layout__main">
        <Outlet />
      </main>
      <footer className="guest-layout__footer">
        <SafetyNotice compact />
      </footer>
    </div>
  )
}
