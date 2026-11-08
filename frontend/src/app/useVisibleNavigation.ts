import { useMemo } from 'react'

import { useAuth } from '@/shared/auth/useAuth'

import { APP_NAVIGATION, filterNavigation, type NavItem } from './navigation'

/**
 * Hook con UNA responsabilidad (S de SOLID): devolver el menú visible para la sesión.
 * Une la lógica pura (filterNavigation) con el estado de React (useAuth).
 */
export function useVisibleNavigation(): readonly NavItem[] {
  const { hasPermission } = useAuth()
  // useMemo: solo se recalcula si cambian los permisos (hasPermission cambia con el usuario).
  return useMemo(() => filterNavigation(APP_NAVIGATION, hasPermission), [hasPermission])
}
