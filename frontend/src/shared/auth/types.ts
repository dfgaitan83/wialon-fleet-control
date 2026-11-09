/**
 * Tipos de autenticación del frontend (camelCase, ya validados).
 * El JSON crudo del backend (snake_case) se valida y transforma en authApi.ts.
 */

/** Permiso con formato "recurso:acción", igual que require_permission() del backend. */
export type Permission = `${string}:${string}` // ej. "drivers:write", "vehicles:read"

/** Ruta pública del formulario de login (a donde redirige RequireAuth). */
export const LOGIN_PATH = '/login'

/**
 * Catálogo de permisos del backend (app/domain/permissions.py). Sin comodín "*:*":
 * el backend envía al Admin los 13 permisos explícitos, así la UI pregunta siempre
 * por un permiso concreto, igual que el servidor.
 */
export const APP_PERMISSIONS = [
  'dashboard:read',
  'vehicles:read',
  'vehicles:write',
  'drivers:read',
  'drivers:write',
  'passengers:read',
  'passengers:write',
  'assignments:write',
  'history:read',
  'export:csv',
  'users:read',
  'users:write',
  'audit:read',
] as const satisfies readonly Permission[]

/** Usuario autenticado tal como lo usa la UI. */
export interface AuthUser {
  readonly id: string
  readonly email: string
  readonly fullName: string
  readonly role: string // "admin" | "operator" | "viewer" (o roles futuros)
  readonly roleLabel: string // nombre visible: "Administrador"...
  readonly permissions: readonly Permission[] // readonly: la UI nunca los modifica
  readonly mustChangePassword: boolean // RF-06: obligatorio en el primer inicio de sesión
}

/** Datos del formulario de login. */
export interface LoginCredentials {
  readonly email: string
  readonly password: string
}

/**
 * PUERTO de autenticación (SOLID):
 * - I (Segregación de interfaces): solo los métodos que AuthProvider necesita.
 * - D (Inversión de dependencias): AuthProvider depende de ESTA interfaz, no de axios
 *   ni de un endpoint concreto. La implementación se inyecta desde app/providers.tsx.
 * - L (Sustitución de Liskov): cualquier implementación (HTTP real, demo en memoria,
 *   fake de tests) debe poder reemplazar a otra sin que AuthProvider cambie.
 *   Contrato: resuelven con datos válidos o rechazan con ApiError.
 *
 * Ningún método devuelve tokens: la sesión vive en cookies HttpOnly que el
 * JavaScript NO puede leer (un XSS no puede robarlas).
 */
export interface AuthService {
  login(credentials: LoginCredentials): Promise<AuthUser>
  me(): Promise<AuthUser>
  logout(): Promise<void>
  changePassword(change: PasswordChange): Promise<AuthUser> // RF-06: devuelve el usuario ya sin la obligación
}

/** Datos del formulario de cambio de contraseña. */
export interface PasswordChange {
  readonly currentPassword: string
  readonly newPassword: string
}

/** Ruta del cambio de contraseña (obligatorio si mustChangePassword). */
export const CHANGE_PASSWORD_PATH = '/cambiar-contrasena'

/**
 * Estado de la sesión:
 * - checking: hay indicio de sesión (cookie CSRF) y se valida con /auth/me (tras un F5).
 * - authenticated: sesión válida y usuario cargado.
 * - anonymous: sin sesión.
 */
export type AuthStatus = 'checking' | 'authenticated' | 'anonymous'

/** Lo que expone el contexto de autenticación a toda la app (vía useAuth()). */
export interface AuthContextValue {
  readonly status: AuthStatus
  readonly user: AuthUser | null
  readonly login: (credentials: LoginCredentials) => Promise<void>
  readonly logout: () => Promise<void>
  readonly changePassword: (change: PasswordChange) => Promise<void>
  readonly hasPermission: (permission: Permission) => boolean
}
