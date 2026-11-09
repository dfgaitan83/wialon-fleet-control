/**
 * Protección CSRF del lado del cliente ("double submit", SEG-11).
 *
 * El backend crea la cookie `fleet_csrf` (NO HttpOnly, a propósito) al iniciar
 * sesión. En cada petición que modifica datos, el cliente copia su valor en la
 * cabecera `X-CSRF-Token`. Un sitio malicioso puede hacer que el navegador ENVÍE
 * nuestras cookies, pero no puede LEERLAS para copiar el valor: su petición
 * llega sin la cabecera correcta y el backend la rechaza con 403.
 *
 * Los tokens de sesión (fleet_access / fleet_refresh) son HttpOnly: este archivo
 * NO puede verlos, y ese es justamente el objetivo.
 */
export const CSRF_COOKIE = 'fleet_csrf'
export const CSRF_HEADER = 'X-CSRF-Token'

const SAFE_METHODS = new Set(['get', 'head', 'options'])

/** Lee una cookie por nombre (null si no existe). */
export function readCookie(name: string): string | null {
  const prefix = `${name}=`
  const match = document.cookie.split('; ').find((part) => part.startsWith(prefix))
  return match ? decodeURIComponent(match.slice(prefix.length)) : null
}

/** ¿El método modifica datos? Solo esos necesitan la cabecera CSRF. */
export function needsCsrf(method: string | undefined): boolean {
  return !SAFE_METHODS.has((method ?? 'get').toLowerCase())
}

/**
 * ¿Hay indicio de una sesión abierta? La cookie CSRF solo existe mientras hay sesión
 * (misma vida que el refresh token). Sin ella no tiene sentido llamar a /auth/me:
 * la landing carga al instante y sin peticiones para los visitantes anónimos.
 */
export function hasSessionHint(): boolean {
  return readCookie(CSRF_COOKIE) !== null
}
