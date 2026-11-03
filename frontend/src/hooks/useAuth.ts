import { useAppAuth } from '../app/Providers'

export function useAuth() {
  return useAppAuth().auth
}

export function useClerkReady() {
  return useAppAuth().clerkReady
}
