/**
 * Proveedores globales de la app (raíz de composición del frontend).
 *
 * - QueryClientProvider (TanStack Query, ARQ-10): estado del SERVIDOR con caché,
 *   reintentos e invalidación tras cada cambio. El estado de UI (formularios,
 *   filtros) vive en los componentes: nunca se duplica en un store global.
 * - AuthProvider recibe el servicio elegido en authService.ts (HTTP real o demo).
 */
import { QueryClientProvider } from '@tanstack/react-query'
import { type ReactNode, useState } from 'react'

import { AuthProvider } from '@/shared/auth/AuthProvider'

import { authService } from './authService'
import { createQueryClient } from './queryClient'

interface AppProvidersProps {
  readonly children: ReactNode
}

export function AppProviders({ children }: AppProvidersProps) {
  const [queryClient] = useState(createQueryClient) // una sola instancia por app
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider service={authService}>{children}</AuthProvider>
    </QueryClientProvider>
  )
}
