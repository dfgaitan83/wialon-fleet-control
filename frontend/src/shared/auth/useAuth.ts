import { useContext } from 'react'

import { AuthContext } from './AuthContext'
import type { AuthContextValue } from './types'

/**
 * Hook para leer la sesión desde cualquier componente:
 *   const { user, login, logout, hasPermission } = useAuth()
 */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  // Falla rápido y con mensaje claro si se olvidó envolver la app en <AuthProvider>.
  if (context === null) throw new Error('useAuth debe usarse dentro de <AuthProvider>')
  return context
}
