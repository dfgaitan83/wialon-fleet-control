/**
 * Implementación DEMO (en memoria) del puerto AuthService.
 *
 * ¿Para qué? El backend aún no tiene /auth/login (meta M2). Para poder ver y
 * revisar el AppLayout en `npm run dev:demo`, se inyecta este servicio en lugar
 * del HTTP real. Es el ejemplo vivo de:
 * - Sustitución de Liskov: cumple el MISMO contrato que authApi; AuthProvider
 *   no nota la diferencia.
 * - Inversión de dependencias: cambiar de implementación no toca AuthProvider.
 *
 * ⚠ SEGURIDAD: solo se usa si import.meta.env.DEV es true (ver app/authService.ts).
 * En `npm run build` (producción) DEV es false y Vite ELIMINA este módulo del
 * bundle (tree-shaking). Verificable: buscar "DEMO_ADMIN" en dist/ no da resultados.
 */
import { ApiError } from '@/shared/api/problem'

import type { AuthService, AuthUser, LoginCredentials, LoginResult } from './types'

const DEMO_TOKEN = 'demo-token' // valor ficticio: nunca llega a ningún servidor
const DEMO_LATENCY_MS = 350 // simula la red para ver estados de carga reales

const DEMO_ADMIN: AuthUser = {
  id: 'demo-admin',
  email: 'admin@demo.local',
  fullName: 'Administrador (demo)',
  permissions: ['*:*'], // comodín: ve todos los módulos del menú
}

const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))

export const demoAuthService: AuthService = {
  async login({ email, password }: LoginCredentials): Promise<LoginResult> {
    await wait(DEMO_LATENCY_MS)
    // Mismo comportamiento que el real ante datos vacíos: rechaza con ApiError (contrato L).
    if (!email || !password) throw new ApiError(401, 'Email o contraseña incorrectos')
    return { accessToken: DEMO_TOKEN, user: { ...DEMO_ADMIN, email } } // copia nueva (inmutable)
  },

  async me(): Promise<AuthUser> {
    await wait(DEMO_LATENCY_MS)
    return DEMO_ADMIN
  },
}
