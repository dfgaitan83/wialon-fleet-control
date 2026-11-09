/**
 * Reglas de permisos en el frontend.
 *
 * ⚠ IMPORTANTE (para sustentar): esto es solo EXPERIENCIA DE USUARIO (ocultar
 * botones o pantallas que el usuario no puede usar). La SEGURIDAD REAL está en
 * el backend (require_permission en backend/app/api/deps.py), porque cualquiera
 * puede modificar el JavaScript de su navegador. El backend siempre vuelve a verificar.
 */
import type { AuthUser, Permission } from './types'

/** ¿Tiene el usuario este permiso? Función pura: fácil de probar y reutilizar. */
export function userHasPermission(user: AuthUser | null, permission: Permission): boolean {
  if (user === null) return false // sin sesión no hay permisos
  return user.permissions.includes(permission) // permiso explícito: igual que el backend
}
