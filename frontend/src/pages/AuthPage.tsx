import { ArrowLeft, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Brand } from '../components/Brand'
import { Button, SafetyNotice } from '../components/Ui'
import { demoImages } from '../data/mockData'

export function AuthPage({ mode }: { mode: 'sign-in' | 'sign-up' }) {
  const [notice, setNotice] = useState('')
  const navigate = useNavigate()
  const isSignUp = mode === 'sign-up'

  function submitForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setNotice('Clerk authentication is not connected in this visual prototype. Continue to the demo workspace to explore the registered-user screens.')
  }

  return (
    <main className="auth-page">
      <aside className="auth-aside">
        <Link to="/"><Brand /></Link>
        <div className="auth-aside__copy">
          <p className="landing-kicker"><span /> INSPECTION SUPPORT</p>
          <h2>Keep every observation connected to its source.</h2>
          <p>Review photographs, model predictions and your inspection notes together in one clear workspace.</p>
          <div className="auth-aside__art">
            <img src={demoImages.overlay} alt="Sample crack overlay in an inspection record" />
          </div>
        </div>
        <div className="auth-aside__foot">AI-assisted predictions · Human-reviewed inspection</div>
      </aside>
      <section className="auth-form-wrap">
        <div className="auth-form">
          <div className="auth-form__top">
            <span>{isSignUp ? 'Already have an account?' : 'New to CrackSight?'}</span>
            <Link to={isSignUp ? '/sign-in' : '/sign-up'}>{isSignUp ? 'Sign in' : 'Create account'}</Link>
          </div>
          <Link className="upload-back" to="/"><ArrowLeft size={14} /> Back to home</Link>
          <h1>{isSignUp ? 'Create your account' : 'Welcome back'}</h1>
          <p className="auth-form__subtitle">
            {isSignUp ? 'Set up your inspection workspace.' : 'Sign in to continue to your workspace.'}
          </p>
          <form className="auth-form__fields" onSubmit={submitForm}>
            {isSignUp && (
              <div className="form-field">
                <label htmlFor="full-name">Full name</label>
                <input id="full-name" name="name" autoComplete="name" placeholder="Jordan Miller" required />
              </div>
            )}
            <div className="form-field">
              <label htmlFor="email">Email address</label>
              <input id="email" name="email" type="email" autoComplete="email" placeholder="you@company.com" required />
            </div>
            <div className="form-field">
              <label htmlFor="password">Password</label>
              <input id="password" name="password" type="password" autoComplete={isSignUp ? 'new-password' : 'current-password'} placeholder="At least 8 characters" minLength={8} required />
            </div>
            <Button type="submit">{isSignUp ? 'Create account' : 'Sign in'}</Button>
          </form>
          <div className="auth-form__separator">or continue with</div>
          <Button
            type="button"
            variant="secondary"
            className="auth-form__google"
            leading={<span className="google-mark" aria-hidden="true">G</span>}
            onClick={() => setNotice('Google sign-in is provided by Clerk in the production integration and is not connected in this prototype.')}
          >
            Continue with Google
          </Button>
          {notice && <p className="prototype-alert" role="status">{notice}</p>}
          <p className="auth-form__bottom">
            By continuing, you agree to use CrackSight AI as an inspection aid. Predictions are not
            a structural safety assessment.
          </p>
          <div style={{ marginTop: 18 }}>
            <SafetyNotice compact />
          </div>
          <button className="button button--ghost auth-demo-link" onClick={() => navigate('/app')}>
            <ShieldCheck size={14} /> Continue to the demo workspace
          </button>
        </div>
      </section>
    </main>
  )
}
