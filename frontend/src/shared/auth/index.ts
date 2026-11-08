// Punto de entrada público de shared/auth: las features importan desde '@/shared/auth'.
export { AuthProvider } from './AuthProvider'
export { userHasPermission } from './permissions'
export { RequireAuth } from './RequireAuth'
export { RequirePermission } from './RequirePermission'
export { tokenStorage } from './tokenStorage'
export {
  ALL_PERMISSIONS,
  LOGIN_PATH,
  type AuthStatus,
  type AuthUser,
  type LoginCredentials,
  type Permission,
} from './types'
export { useAuth } from './useAuth'
