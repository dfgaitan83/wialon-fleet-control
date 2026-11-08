/**
 * Llamadas de autenticación al backend y CONTRATO que el backend debe cumplir.
 *
 * ⚠ Estado: estos endpoints AÚN NO existen en el backend (hoy solo hay /health).
 * Este archivo define el contrato; el backend lo implementará en su meta de auth:
 *
 *   POST /api/v1/auth/login   body: { "email": "...", "password": "..." }
 *     200 -> { "access_token": "<jwt>", "token_type": "bearer",
 *              "user": { "id": "1", "email": "...", "full_name": "...", "permissions": ["*:*"] } }
 *     401 -> Problem Details (credenciales incorrectas)
 *
 *   GET  /api/v1/auth/me      header: Authorization: Bearer <jwt>
 *     200 -> { "id": "1", "email": "...", "full_name": "...", "permissions": [...] }
 *     401 -> Problem Details (token inválido o expirado)
 *
 * ¿Por qué validar con zod? "Nunca confiar en datos externos": si el backend
 * cambia un campo, se detecta AQUÍ con un error claro y no como un "undefined"
 * misterioso en mitad de la UI.
 */
import { z } from 'zod'

import { apiClient } from '@/shared/api/client'
import { ApiError } from '@/shared/api/problem'

import type { AuthService, AuthUser, LoginCredentials, LoginResult, Permission } from './types'

const INVALID_RESPONSE_STATUS = 502 // "Bad Gateway": el servidor respondió algo inesperado

// --- Esquemas del JSON CRUDO del backend (snake_case) ---
const userDtoSchema = z.object({
  id: z.union([z.string(), z.number()]).transform(String), // acepta id numérico o texto
  email: z.email(),
  full_name: z.string(),
  permissions: z.array(z.string().regex(/^[^:]+:[^:]+$/)), // formato "recurso:acción"
})

const loginResponseSchema = z.object({
  access_token: z.string().min(1),
  token_type: z.string().toLowerCase().pipe(z.literal('bearer')), // solo aceptamos Bearer
  user: userDtoSchema,
})

type UserDto = z.infer<typeof userDtoSchema>

/** DTO del backend (snake_case) -> modelo de la UI (camelCase). */
function toAuthUser(dto: UserDto): AuthUser {
  return {
    id: dto.id,
    email: dto.email,
    fullName: dto.full_name,
    permissions: dto.permissions as Permission[], // el regex ya garantizó el formato
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
  /** Inicia sesión. Errores (401, red...) llegan como ApiError gracias al interceptor. */
  async login(credentials: LoginCredentials): Promise<LoginResult> {
    const { data } = await apiClient.post<unknown>('/auth/login', credentials) // unknown: se valida abajo
    const parsed = parseOrThrow(loginResponseSchema, data)
    return { accessToken: parsed.access_token, user: toAuthUser(parsed.user) }
  },

  /** Usuario de la sesión actual (se usa tras recargar la página). */
  async me(): Promise<AuthUser> {
    const { data } = await apiClient.get<unknown>('/auth/me')
    return toAuthUser(parseOrThrow(userDtoSchema, data))
  },
}
