/**
 * Cliente HTTP único del frontend (axios + interceptores).
 *
 * Toda llamada al backend pasa por aquí. Ventajas:
 * - La URL base, el timeout y las cabeceras se configuran en UN solo lugar.
 * - Interceptor de PETICIÓN: añade "Authorization: Bearer <token>" automáticamente.
 * - Interceptor de RESPUESTA: convierte todo error en ApiError (Problem Details)
 *   y, ante un 401, avisa a la capa de auth para cerrar la sesión.
 *
 * Importante: el frontend SOLO habla con NUESTRO backend, nunca con Wialon. El
 * token de Wialon vive exclusivamente en backend/.env.
 */
import axios, { type InternalAxiosRequestConfig } from 'axios'

import { tokenStorage } from '@/shared/auth/tokenStorage'

import { toApiError } from './problem'

const DEFAULT_BASE_URL = 'http://localhost:8000/api/v1' // backend local en desarrollo
const REQUEST_TIMEOUT_MS = 15_000 // igual que el timeout del backend hacia Wialon

// Rutas donde un 401 significa "credenciales incorrectas", NO "sesión expirada".
// En ellas no se debe disparar el cierre de sesión automático.
const AUTH_ENDPOINTS_WITHOUT_LOGOUT = ['/auth/login'] as const

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? DEFAULT_BASE_URL, // se cambia por entorno, no en código
  timeout: REQUEST_TIMEOUT_MS,
  headers: { Accept: 'application/json' },
})

// ---------------------------------------------------------------------------
// Aviso de 401. ¿Por qué un "handler" registrable y no importar AuthProvider?
// Porque AuthProvider ya importa este cliente: importarlo aquí crearía un ciclo.
// En su lugar, AuthProvider se registra con setUnauthorizedHandler(logout).
// ---------------------------------------------------------------------------
type UnauthorizedHandler = () => void
let unauthorizedHandler: UnauthorizedHandler | null = null

/** Registra la función a llamar cuando el backend responde 401 (sesión expirada). Devuelve cómo quitarla. */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): () => void {
  unauthorizedHandler = handler
  return () => {
    if (unauthorizedHandler === handler) unauthorizedHandler = null // limpieza al desmontar
  }
}

function isAuthEndpoint(config: InternalAxiosRequestConfig | undefined): boolean {
  const url = config?.url ?? ''
  return AUTH_ENDPOINTS_WITHOUT_LOGOUT.some((path) => url.endsWith(path))
}

// --- Interceptor de PETICIÓN: adjunta el token si existe ---
apiClient.interceptors.request.use((config) => {
  const token = tokenStorage.get()
  if (token) config.headers.set('Authorization', `Bearer ${token}`) // esquema Bearer (JWT)
  return config // siempre devolver la config (si no, axios no envía la petición)
})

// --- Interceptor de RESPUESTA: normaliza errores ---
apiClient.interceptors.response.use(
  (response) => response, // éxito: se deja pasar tal cual
  (error: unknown) => {
    const apiError = toApiError(error) // red, timeout, 4xx, 5xx -> ApiError
    const config = axios.isAxiosError(error) ? error.config : undefined
    // 401 fuera de /auth/login = token inválido o expirado -> cerrar sesión.
    if (apiError.status === 401 && !isAuthEndpoint(config)) unauthorizedHandler?.()
    return Promise.reject(apiError) // quien llamó recibe SIEMPRE un ApiError
  },
)
