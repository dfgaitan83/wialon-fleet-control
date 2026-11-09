/**
 * Arranque en frío del backend (DEP-04).
 *
 * El plan gratuito de Render apaga el servidor tras 15 min sin uso y tarda unos
 * 30-60 s en despertar. Sin esto, la primera petición agota el timeout y el
 * usuario ve "No se pudo conectar". Con esto:
 *   1. se hace ping a /health con espera creciente (1, 2, 4, 8, 16, 16... s ≈ 95 s);
 *   2. mientras tanto el estado es "waking" -> la UI muestra "Iniciando el servidor";
 *   3. si responde -> "ready" (y no se vuelve a esperar); si se agota -> "down"
 *      con opción de reintentar.
 *
 * Single-flight: si login y /me piden esperar a la vez, comparten UN solo ping.
 * Dependencias inyectables (ping, sleep, esperas): los tests no esperan de verdad.
 */
import { ApiError, NETWORK_ERROR_STATUS } from '@/shared/api/problem'

export type BackendStatus = 'unknown' | 'checking' | 'waking' | 'ready' | 'down'

/** Resultado de un ping: código HTTP recibido, o null si no hubo respuesta (red/timeout). */
export type PingFn = () => Promise<number | null>

// 1+2+4+8+16 y luego 16 s fijos: ~95 s en total, más que un arranque en frío típico.
export const WAKE_DELAYS_MS = [1_000, 2_000, 4_000, 8_000, 16_000, 16_000, 16_000, 16_000, 16_000] as const
// Códigos que Render/Vercel devuelven mientras el servicio arranca: aún NO está listo.
const STARTING_STATUSES = new Set([502, 503, 504])

interface WakeupDeps {
  readonly ping: PingFn
  readonly sleep?: (ms: number) => Promise<void>
  readonly delays?: readonly number[]
}

export interface BackendWakeup {
  getStatus(): BackendStatus
  subscribe(listener: () => void): () => void
  ensureReady(): Promise<void> // resuelve cuando el backend responde; rechaza con ApiError si se agota
  retry(): Promise<void> // tras "down": vuelve a intentarlo desde cero
}

const defaultSleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))

/** ¿El backend está despierto? Cualquier respuesta HTTP salvo 502/503/504 (incluso 401/404). */
function isAwake(status: number | null): boolean {
  return status !== null && !STARTING_STATUSES.has(status)
}

export function createBackendWakeup({ ping, sleep = defaultSleep, delays = WAKE_DELAYS_MS }: WakeupDeps): BackendWakeup {
  let status: BackendStatus = 'unknown'
  let inFlight: Promise<void> | null = null
  const listeners = new Set<() => void>()

  const setStatus = (next: BackendStatus) => {
    status = next
    listeners.forEach((listener) => listener())
  }

  async function wake(): Promise<void> {
    setStatus('checking')
    if (isAwake(await ping())) return setStatus('ready')
    setStatus('waking') // el primer intento falló: es un arranque en frío, avisar al usuario
    for (const delay of delays) {
      await sleep(delay)
      if (isAwake(await ping())) return setStatus('ready')
    }
    setStatus('down')
    throw new ApiError(
      NETWORK_ERROR_STATUS,
      'El servidor no respondió a tiempo. Revisa tu conexión e inténtalo de nuevo.',
    )
  }

  const ensureReady = (): Promise<void> => {
    if (status === 'ready') return Promise.resolve()
    inFlight ??= wake().finally(() => {
      inFlight = null
    })
    return inFlight
  }

  return {
    getStatus: () => status,
    subscribe(listener) {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    ensureReady,
    retry: () => {
      if (status === 'down') status = 'unknown'
      return ensureReady()
    },
  }
}
