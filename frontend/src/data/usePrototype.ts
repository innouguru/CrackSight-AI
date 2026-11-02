import { useContext } from 'react'
import { PrototypeContext } from './prototype-context'

export function usePrototype() {
  const context = useContext(PrototypeContext)
  if (!context) {
    throw new Error('usePrototype must be used within PrototypeProvider')
  }
  return context
}
