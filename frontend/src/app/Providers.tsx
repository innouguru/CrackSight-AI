import { createContext, useContext, type ReactNode } from 'react'
import {
  ClerkProvider,
  useAuth as useClerkAuth,
  useUser as useClerkUser,
  useSignIn as useClerkSignIn,
  useSignUp as useClerkSignUp,
} from '@clerk/clerk-react'
import type { AuthState } from '../types'

interface ProvidersProps {
  children: ReactNode
}

const clerkPublishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY

interface AppContextValue {
  auth: AuthState
  clerkReady: boolean
}

const AppContext = createContext<AppContextValue | null>(null)

export function AppProviders({ children }: ProvidersProps) {
  const { isSignedIn, isLoaded, getToken, signOut } = useClerkAuth()
  const { signIn } = useClerkSignIn()
  const { signUp } = useClerkSignUp()
  const { user } = useClerkUser()
  const clerkReady = isLoaded

  const authenticated = isSignedIn ?? false

  const auth: AuthState = {
    user: {
      user_id: user?.id ?? null,
      email: user?.primaryEmailAddress?.emailAddress ?? null,
      is_guest: false,
      is_authenticated: authenticated,
      guest_session_id: null,
    },
    isAuthenticated: authenticated,
    isGuest: false,
    isLoading: !clerkReady,
    signIn: (emailAddress, password) => {
      void signIn?.create({ strategy: 'password', identifier: emailAddress, password })
    },
    signUp: (emailAddress, password, firstName) => {
      void signUp?.create({ emailAddress, password, firstName })
    },
    signInWithGoogle: () => {
      void signIn?.authenticateWithRedirect({ strategy: 'oauth_google', redirectUrl: '/', redirectUrlComplete: '/' })
    },
    signOut: () => {
      void signOut()
    },
    getToken: async () => {
      if (!authenticated) return null
      return getToken()
    },
  }

  if (!clerkPublishableKey) {
    console.warn(
      'Clerk publishable key is not configured. Set VITE_CLERK_PUBLISHABLE_KEY in your .env file.',
    )
  }

  return (
    <ClerkProvider publishableKey={clerkPublishableKey}>
      <AppContext.Provider value={{ auth, clerkReady }}>
        {children}
      </AppContext.Provider>
    </ClerkProvider>
  )
}

export function useAppAuth() {
  const context = useContext(AppContext)
  if (!context) {
    throw new Error('useAppAuth must be used within AppProviders')
  }
  return context
}

export function useClerkReady() {
  const context = useContext(AppContext)
  if (!context) {
    throw new Error('useClerkReady must be used within AppProviders')
  }
  return context.clerkReady
}
