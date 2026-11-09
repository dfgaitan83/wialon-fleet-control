/**
 * Usuarios de prueba con la forma EXACTA del backend (UserOut, snake_case) y de la UI.
 */
import { APP_PERMISSIONS, type AuthUser, type Permission } from '@/shared/auth/types'

/** DTO tal como lo envía GET /auth/me (y dentro de { user } en login). */
export function userDto(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    email: 'admin@demo.co',
    full_name: 'Admin Demo',
    role: 'admin',
    role_label: 'Administrador',
    permissions: [...APP_PERMISSIONS],
    must_change_password: false,
    ...overrides,
  }
}

/** Usuario ya transformado para la UI (camelCase). */
export function authUser(permissions: readonly Permission[] = APP_PERMISSIONS): AuthUser {
  return {
    id: '1',
    email: 'ana@flota.co',
    fullName: 'Ana Gómez',
    role: 'admin',
    roleLabel: 'Administrador',
    permissions,
    mustChangePassword: false,
  }
}
