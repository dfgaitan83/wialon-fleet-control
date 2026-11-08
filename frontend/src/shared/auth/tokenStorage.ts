/**
 * Almacenamiento del token de acceso (JWT) del usuario.
 *
 * DECISIÓN DE SEGURIDAD (para sustentar): ¿dónde guardar el token?
 * - localStorage: sobrevive para siempre y cualquier script inyectado (XSS) lo lee. ❌
 * - Solo memoria: lo más seguro, pero se pierde al recargar la página (F5). Incómodo.
 * - sessionStorage + memoria (ELEGIDO): la memoria es la fuente principal; sessionStorage
 *   solo permite sobrevivir a un F5 y se BORRA al cerrar la pestaña. Tampoco se
 *   comparte entre pestañas.
 * - Cookie httpOnly: lo ideal (JavaScript no puede leerla), pero exige que el backend
 *   la emita y protección CSRF. Este módulo es el ÚNICO punto a cambiar si se migra.
 *
 * Solo se guarda el TOKEN, nunca el usuario ni sus permisos: al recargar se piden
 * de nuevo a /auth/me, porque el servidor es la única fuente de verdad.
 */

const STORAGE_KEY = 'wfc.access_token' // prefijo "wfc" (Wialon Fleet Control) evita choques

let memoryToken: string | null = null // copia en memoria: lectura rápida y principal

// sessionStorage puede lanzar excepción (modo privado, almacenamiento bloqueado):
// por eso todo acceso va en try/catch y la app sigue funcionando solo con memoria.
function readSession(): string | null {
  try {
    return sessionStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

function writeSession(token: string | null): void {
  try {
    if (token === null) sessionStorage.removeItem(STORAGE_KEY)
    else sessionStorage.setItem(STORAGE_KEY, token)
  } catch {
    // Sin sessionStorage disponible: la sesión durará hasta recargar. Es aceptable.
  }
}

export const tokenStorage = {
  /** Token actual: primero memoria; si no hay (tras un F5), se recupera de sessionStorage. */
  get(): string | null {
    memoryToken ??= readSession() // ??= asigna solo si memoryToken es null
    return memoryToken
  },
  /** Guarda el token tras un login correcto. */
  set(token: string): void {
    memoryToken = token
    writeSession(token)
  },
  /** Borra el token (logout o sesión expirada). */
  clear(): void {
    memoryToken = null
    writeSession(null)
  },
} as const
