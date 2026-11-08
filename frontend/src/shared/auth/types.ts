/**
 * Tipos de autenticación del frontend (camelCase, ya validados).
 * El JSON crudo del backend (snake_case) se valida y transforma en authApi.ts.
 */

/** Permiso con formato "recurso:acción", igual que require_permission() del backend. */
export type Permission = `${string}:${string}` // ej. "drivers:write", "vehicles:read"

/** Ruta pública del formulario de login (a donde redirige RequireAuth). */
export const LOGIN_PATH = '/login'

/** Comodín: el administrador tiene todos los permisos. */
export const ALL_PERMISSIONS = '*:*' satisfies Permission

/** Usuario autenticado tal como lo usa la UI. */
export interface AuthUser {
  readonly id: string
  readonly email: string
  readonly fullName: string
  readonly permissions: readonly Permission[] // readonly: la UI nunca los modifica
}

/** Datos del formulario de login. */
export interface LoginCredentials {
  readonly email: string
  readonly password: string
}

/** Resultado de un login correcto. */
export interface LoginResult {
  readonly accessToken: string
  readonly user: AuthUser
}

/**
 * PUERTO de autenticación (SOLID):
 * - I (Segregación de interfaces): solo los DOS métodos que AuthProvider necesita.
 * - D (Inversión de dependencias): AuthProvider depende de ESTA interfaz, no de axios
 *   ni de un endpoint concreto. La implementación se inyecta desde app/providers.tsx.
 * - L (Sustitución de Liskov): cualquier implementación (HTTP real, demo en memoria,
 *   fake de tests) debe poder reemplazar a otra sin que AuthProvider cambie.
 *   Contrato: login/me resuelven con datos válidos o rechazan con ApiError.
 */
export interface AuthService {
  login(credentials: LoginCredentials): Promise<LoginResult>
  me(): Promise<AuthUser>
}

/**
 * Estado de la sesión:
 * - checking: hay token guardado y se está validando con /auth/me (tras un F5).
 * - authenticated: sesión válida y usuario cargado.
 * - anonymous: sin sesión.
 */
export type AuthStatus = 'checking' | 'authenticated' | 'anonymous'

/** Lo que expone el contexto de autenticación a toda la app (vía useAuth()). */
export interface AuthContextValue {
  readonly status: AuthStatus
  readonly user: AuthUser | null
  readonly login: (credentials: LoginCredentials) => Promise<void>
  readonly logout: () => void
  readonly hasPermission: (permission: Permission) => boolean
}
