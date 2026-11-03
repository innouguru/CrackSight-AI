import { ArrowLeft, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Brand } from '../components/Brand'
import { Button, SafetyNotice } from '../components/Ui'
import { demoImages } from '../data/mockData'
import { useAuth } from '../hooks/useAuth'

export function AuthPage({ mode }: { mode: 'sign-in' | 'sign-up' }) {
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const isSignUp = mode === 'sign-up'
  const { signIn, signUp, signInWithGoogle, isLoading } = useAuth()

  async function submitForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setNotice('')

    const formData = new FormData(event.currentTarget)
    const email = formData.get('email') as string
    const password = formData.get('password') as string
    const name = formData.get('name') as string

    try {
      if (isSignUp) {
        await signUp(email, password, name)
        setNotice('Account created. Please check your email to verify your address, then sign in.')
      } else {
        await signIn(email, password)
        navigate('/app')
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Authentication failed. Please try again.'
      setError(message)
    }
  }

  function handleGoogleSignIn() {
    setError('')
    setNotice('')
    void signInWithGoogle()
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
          {isLoading && (
            <div className="prototype-alert" role="status">
              Signing in…
            </div>
          )}
          {!isLoading && (
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
              <Button type="submit" disabled={isLoading}>
                {isSignUp ? 'Create account' : 'Sign in'}
              </Button>
            </form>
          )}
          <div className="auth-form__separator">or continue with</div>
          <Button
            type="button"
            variant="secondary"
            className="auth-form__google"
            leading={<span className="google-mark" aria-hidden="true">G</span>}
            onClick={handleGoogleSignIn}
            disabled={isLoading}
          >
            Continue with Google
          </Button>
          {error && <p className="prototype-alert" role="alert">{error}</p>}
          {notice && <p className="prototype-alert" role="status">{notice}</p>}
          {!isLoading && (
            <p className="auth-form__bottom">
              By continuing, you agree to use CrackSight AI as an inspection aid. Predictions are not
              a structural safety assessment.
            </p>
          )}
          <div style={{ marginTop: 18 }}>
            <SafetyNotice compact />
          </div>
          {!isLoading && (
            <button className="button button--ghost auth-demo-link" onClick={() => navigate('/try')}>
              <ShieldCheck size={14} /> Continue as guest
            </button>
          )}
        </div>
      </section>
    </main>
  )
}
