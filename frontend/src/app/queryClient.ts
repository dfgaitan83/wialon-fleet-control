/**
 * Cliente de TanStack Query (ARQ-10): estado del SERVIDOR con caché e invalidación.
 * En archivo propio (no en providers.tsx) para que los tests creen instancias aisladas
 * y para que el componente de providers solo exporte componentes (fast refresh).
 */
import { QueryClient } from '@tanstack/react-query'

import { ApiError } from '@/shared/api/problem'

const STALE_TIME_MS = 15_000 // mismo TTL que la caché del backend hacia Wialon
const MAX_RETRIES = 2

/** No reintentar errores del cliente (4xx): repetirlos no cambia el resultado. */
function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false
  return failureCount < MAX_RETRIES
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { staleTime: STALE_TIME_MS, retry: shouldRetry, refetchOnWindowFocus: false },
      mutations: { retry: false }, // una escritura NUNCA se repite sola (evita duplicados)
    },
  })
}
