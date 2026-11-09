/**
 * Implementación DEMO (en memoria) del puerto AuthService.
 *
 * ¿Para qué? Revisar la interfaz con `npm run dev:demo` sin backend. Es el ejemplo vivo de:
 * - Sustitución de Liskov: cumple el MISMO contrato que authApi; AuthProvider
 *   no nota la diferencia (ver authService.contract.test.ts).
 * - Inversión de dependencias: cambiar de implementación no toca AuthProvider.
 *
 * ⚠ SEGURIDAD: solo se usa si import.meta.env.DEV es true (ver app/authService.ts).
 * En `npm run build` (producción) DEV es false y Vite ELIMINA este módulo del
 * bundle (tree-shaking). Verificable: buscar "DEMO_ADMIN" en dist/ no da resultados.
 */
import { ApiError } from '@/shared/api/problem'

import {
  APP_PERMISSIONS,
  type AuthService,
  type AuthUser,
  type LoginCredentials,
  type PasswordChange,
} from './types'

const DEMO_LATENCY_MS = 350 // simula la red para ver estados de carga reales

const DEMO_ADMIN: AuthUser = {
  id: 'demo-admin',
  email: 'admin@demo.local',
  fullName: 'Administrador (demo)',
  role: 'admin',
  roleLabel: 'Administrador',
  permissions: APP_PERMISSIONS, // mismos permisos explícitos que envía el backend al Admin
  mustChangePassword: false,
}

const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))

export const demoAuthService: AuthService = {
  async login({ email, password }: LoginCredentials): Promise<AuthUser> {
    await wait(DEMO_LATENCY_MS)
    // Mismo comportamiento que el real ante datos vacíos: rechaza con ApiError (contrato L).
    if (!email || !password) throw new ApiError(401, 'Correo o contraseña incorrectos')
    return { ...DEMO_ADMIN, email } // copia nueva (inmutable)
  },

  async me(): Promise<AuthUser> {
    await wait(DEMO_LATENCY_MS)
    return DEMO_ADMIN
  },

  async logout(): Promise<void> {
    await wait(DEMO_LATENCY_MS)
  },

  async changePassword({ currentPassword, newPassword }: PasswordChange): Promise<AuthUser> {
    await wait(DEMO_LATENCY_MS)
    if (!currentPassword || !newPassword) {
      throw new ApiError(422, 'Revisa los datos del formulario.')
    }
    return { ...DEMO_ADMIN, mustChangePassword: false }
  },
}
