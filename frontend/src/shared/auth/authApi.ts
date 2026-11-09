/**
 * Llamadas de autenticación al backend (/api/v1/auth) y validación de su contrato.
 *
 * Contrato (ver backend/app/api/v1/auth.py y Swagger):
 *   POST /auth/login   { email, password } -> 200 { user: UserOut } + cookies de sesión
 *                                          -> 401 Problem Details (mensaje genérico)
 *   GET  /auth/me                          -> 200 UserOut | 401
 *   POST /auth/logout  (X-CSRF-Token)      -> 204, el servidor invalida la sesión
 *   UserOut = { id, email, full_name, role, role_label, permissions[], must_change_password }
 *
 * Los tokens NUNCA llegan en el cuerpo: viajan en cookies HttpOnly.
 *
 * ¿Por qué validar con zod? "Nunca confiar en datos externos": si el backend
 * cambia un campo, se detecta AQUÍ con un error claro y no como un "undefined"
 * misterioso en mitad de la UI.
 */
import { z } from 'zod'

import { apiClient } from '@/shared/api/client'
import { ApiError } from '@/shared/api/problem'
import { backendWakeup } from '@/shared/server/backendStatus'

import type { AuthService, AuthUser, LoginCredentials, Permission } from './types'

const INVALID_RESPONSE_STATUS = 502 // "Bad Gateway": el servidor respondió algo inesperado

// --- Esquemas del JSON CRUDO del backend (snake_case) ---
const userDtoSchema = z.object({
  id: z.union([z.string(), z.number()]).transform(String), // acepta id numérico o texto
  email: z.email(),
  full_name: z.string(),
  role: z.string(),
  role_label: z.string(),
  permissions: z.array(z.string().regex(/^[^:]+:[^:]+$/)), // formato "recurso:acción"
  must_change_password: z.boolean(),
})

const sessionSchema = z.object({ user: userDtoSchema })

type UserDto = z.infer<typeof userDtoSchema>

/** DTO del backend (snake_case) -> modelo de la UI (camelCase). */
function toAuthUser(dto: UserDto): AuthUser {
  return {
    id: dto.id,
    email: dto.email,
    fullName: dto.full_name,
    role: dto.role,
    roleLabel: dto.role_label,
    permissions: dto.permissions as Permission[], // el regex ya garantizó el formato
    mustChangePassword: dto.must_change_password,
  }
}

/** Valida una respuesta; si no cumple el contrato lanza ApiError en vez de seguir con datos rotos. */
function parseOrThrow<T>(schema: z.ZodType<T>, data: unknown): T {
  const result = schema.safeParse(data)
  if (!result.success) {
    throw new ApiError(INVALID_RESPONSE_STATUS, 'El servidor respondió en un formato inesperado.')
  }
  return result.data
}

/** Implementación HTTP REAL del puerto AuthService (adaptador hacia nuestro backend). */
export const authApi: AuthService = {
  /** Inicia sesión. El backend responde el usuario y fija las cookies de sesión. */
  async login(credentials: LoginCredentials): Promise<AuthUser> {
    await backendWakeup.ensureReady() // DEP-04: si Render está dormido, esperar a que despierte
    const { data } = await apiClient.post<unknown>('/auth/login', credentials) // unknown: se valida abajo
    return toAuthUser(parseOrThrow(sessionSchema, data).user)
  },

  /** Usuario de la sesión actual (se usa tras recargar la página). */
  async me(): Promise<AuthUser> {
    await backendWakeup.ensureReady()
    const { data } = await apiClient.get<unknown>('/auth/me')
    return toAuthUser(parseOrThrow(userDtoSchema, data))
  },

  /** Cierra la sesión EN EL SERVIDOR (revoca el refresh token y borra las cookies). */
  async logout(): Promise<void> {
    await apiClient.post('/auth/logout')
  },
}
