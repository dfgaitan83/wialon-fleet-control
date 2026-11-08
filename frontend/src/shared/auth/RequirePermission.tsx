/**
 * Muestra su contenido solo si el usuario tiene un permiso concreto.
 *
 * Uso:
 *   <RequirePermission permission="drivers:write">
 *     <Button>Editar conductor</Button>
 *   </RequirePermission>
 *
 * ⚠ Solo UX: el backend vuelve a comprobar el permiso en cada petición (ver permissions.ts).
 */
import type { ReactNode } from 'react'
import { Outlet } from 'react-router-dom'

import { EmptyState } from '@/shared/ui/EmptyState'

import type { Permission } from './types'
import { useAuth } from './useAuth'

interface RequirePermissionProps {
  readonly permission: Permission
  readonly children?: ReactNode // sin children: protege rutas hijas (<Outlet/>)
  readonly fallback?: ReactNode // qué mostrar sin permiso; null = no mostrar nada (ej. un botón)
}

const DEFAULT_FALLBACK = (
  <EmptyState
    title="Acceso restringido"
    description="Tu usuario no tiene permiso para ver esta sección. Contacta a un administrador."
  />
)

export function RequirePermission({
  permission,
  children,
  fallback = DEFAULT_FALLBACK,
}: RequirePermissionProps) {
  const { hasPermission } = useAuth()
  if (!hasPermission(permission)) return fallback
  return children ?? <Outlet />
}
