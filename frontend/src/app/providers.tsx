/**
 * Proveedores globales de la app (raíz de composición del frontend).
 *
 * Aquí se INYECTAN las dependencias concretas: AuthProvider recibe el servicio
 * elegido en authService.ts (HTTP real o demo). En metas siguientes se añadirán
 * aquí el QueryClientProvider (TanStack Query) y el proveedor de notificaciones.
 */
import type { ReactNode } from 'react'

import { AuthProvider } from '@/shared/auth/AuthProvider'

import { authService } from './authService'

interface AppProvidersProps {
  readonly children: ReactNode
}

export function AppProviders({ children }: AppProvidersProps) {
  return <AuthProvider service={authService}>{children}</AuthProvider>
}
