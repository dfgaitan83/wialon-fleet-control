/**
 * Utilidades de tests para simular la cookie CSRF que crea el backend.
 * (Las cookies de sesión son HttpOnly: en el navegador real el JS no las ve,
 * por eso los tests tampoco las necesitan.)
 */
import { CSRF_COOKIE } from '@/shared/api/csrf'

/** Simula una sesión abierta: el backend dejó la cookie CSRF legible. */
export function setCsrfCookie(value = 'csrf-de-prueba'): void {
  document.cookie = `${CSRF_COOKIE}=${value}; path=/`
}

/** Simula un navegador sin sesión. */
export function clearCsrfCookie(): void {
  document.cookie = `${CSRF_COOKIE}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT`
}
