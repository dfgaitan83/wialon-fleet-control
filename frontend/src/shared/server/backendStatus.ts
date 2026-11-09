/**
 * Instancia ÚNICA del detector de arranque en frío, conectada al cliente HTTP real,
 * y el hook de React para leer su estado.
 */
import { useSyncExternalStore } from 'react'

import { apiClient } from '@/shared/api/client'
import { ApiError } from '@/shared/api/problem'

import { type BackendStatus, createBackendWakeup } from './backendWakeup'

const PING_TIMEOUT_MS = 10_000 // cada ping espera hasta 10 s (Render retiene la conexión al despertar)

async function pingHealth(): Promise<number | null> {
  try {
    const response = await apiClient.get('/health', { timeout: PING_TIMEOUT_MS })
    return response.status
  } catch (error: unknown) {
    // ApiError con status 0 = sin respuesta (red/timeout); otro código = el servidor sí respondió.
    if (error instanceof ApiError) return error.isNetworkError ? null : error.status
    return null
  }
}

export const backendWakeup = createBackendWakeup({ ping: pingHealth })

/** Estado del backend para la UI (se re-renderiza al cambiar). */
export function useBackendStatus(): BackendStatus {
  return useSyncExternalStore(backendWakeup.subscribe, backendWakeup.getStatus)
}
