/**
 * Cliente HTTP único del frontend (axios + interceptores, ARQ-09).
 *
 * Toda llamada al backend pasa por aquí. Ventajas:
 * - URL base, timeout y cabeceras en UN solo lugar.
 * - Sesión por COOKIES HttpOnly (withCredentials): el JS nunca toca los tokens.
 * - Interceptor de PETICIÓN: añade `X-CSRF-Token` en las peticiones que modifican datos.
 * - Interceptor de RESPUESTA:
 *     · 401 en una petición normal -> intenta renovar la sesión UNA vez
 *       (POST /auth/refresh) y repite la petición; el usuario no nota nada.
 *     · si la renovación falla -> avisa a la capa de auth para cerrar la sesión.
 *     · todo error se convierte en ApiError (Problem Details).
 *
 * baseURL "/api/v1" (mismo origen): en desarrollo lo reenvía el proxy de Vite y en
 * producción el rewrite de Vercel hacia Render. Así las cookies son de primer nivel
 * (SameSite funciona) y no hace falta CORS en el navegador.
 *
 * Importante: el frontend SOLO habla con NUESTRO backend, nunca con Wialon (INT-02).
 */
import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

import { CSRF_COOKIE, CSRF_HEADER, needsCsrf, readCookie } from './csrf'
import { toApiError } from './problem'

const DEFAULT_BASE_URL = '/api/v1'
const REQUEST_TIMEOUT_MS = 15_000 // > timeout del backend hacia Wialon (10 s) + margen
const REFRESH_PATH = '/auth/refresh'

// Rutas donde un 401 NO significa "sesión expirada, renuévala":
// login (credenciales malas), refresh (la renovación misma falló) y logout.
const AUTH_ENDPOINTS_WITHOUT_REFRESH = ['/auth/login', REFRESH_PATH, '/auth/logout'] as const

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? DEFAULT_BASE_URL, // se cambia por entorno, no en código
  timeout: REQUEST_TIMEOUT_MS,
  withCredentials: true, // envía y recibe las cookies de sesión
  headers: { Accept: 'application/json' },
})

// ---------------------------------------------------------------------------
// Aviso de sesión perdida. ¿Por qué un "handler" registrable y no importar
// AuthProvider? Porque AuthProvider ya importa este cliente: importarlo aquí
// crearía un ciclo. AuthProvider se registra con setUnauthorizedHandler().
// ---------------------------------------------------------------------------
type UnauthorizedHandler = () => void
let unauthorizedHandler: UnauthorizedHandler | null = null

/** Registra la función a llamar cuando la sesión no se puede renovar. Devuelve cómo quitarla. */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): () => void {
  unauthorizedHandler = handler
  return () => {
    if (unauthorizedHandler === handler) unauthorizedHandler = null // limpieza al desmontar
  }
}

interface RetriableConfig extends InternalAxiosRequestConfig {
  _retriedAfterRefresh?: boolean // marca: esta petición ya se repitió una vez (evita bucles)
}

function isAuthEndpoint(config: InternalAxiosRequestConfig | undefined): boolean {
  const url = config?.url ?? ''
  return AUTH_ENDPOINTS_WITHOUT_REFRESH.some((path) => url.endsWith(path))
}

// ---------------------------------------------------------------------------
// Renovación "single-flight": si 10 peticiones reciben 401 a la vez, se hace UN
// solo refresh y las 10 esperan la misma promesa. Varios refresh simultáneos
// serían peligrosos: el backend vería el refresh token reutilizado y cerraría
// la sesión por sospecha de robo (detección de reutilización).
// ---------------------------------------------------------------------------
let refreshInFlight: Promise<void> | null = null

function refreshSession(): Promise<void> {
  refreshInFlight ??= apiClient
    .post(REFRESH_PATH)
    .then(() => undefined)
    .finally(() => {
      refreshInFlight = null
    })
  return refreshInFlight
}

// --- Interceptor de PETICIÓN: cabecera CSRF en métodos que modifican datos ---
apiClient.interceptors.request.use((config) => {
  if (needsCsrf(config.method)) {
    const token = readCookie(CSRF_COOKIE)
    if (token) config.headers.set(CSRF_HEADER, token)
  }
  return config // siempre devolver la config (si no, axios no envía la petición)
})

// --- Interceptor de RESPUESTA: renovación transparente y errores normalizados ---
apiClient.interceptors.response.use(
  (response) => response, // éxito: se deja pasar tal cual
  async (error: unknown) => {
    const config = axios.isAxiosError(error) ? (error.config as RetriableConfig | undefined) : undefined
    const status = axios.isAxiosError(error) ? (error as AxiosError).response?.status : undefined

    if (status === 401 && config && !isAuthEndpoint(config) && !config._retriedAfterRefresh) {
      try {
        await refreshSession()
      } catch {
        unauthorizedHandler?.() // no se pudo renovar: la sesión terminó de verdad
        throw toApiError(error)
      }
      config._retriedAfterRefresh = true
      return apiClient.request(config) // misma petición, ahora con la cookie de acceso nueva
    }

    throw toApiError(error) // quien llamó recibe SIEMPRE un ApiError
  },
)
