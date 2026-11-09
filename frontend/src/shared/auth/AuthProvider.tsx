/**
 * Proveedor de sesión: guarda quién está logueado y lo comparte con toda la app.
 *
 * Ciclo de vida (sesión en cookies HttpOnly: el JS no ve los tokens):
 * 1. Al cargar la app: si existe la cookie CSRF (indicio de sesión, tras un F5)
 *    -> status "checking" y se valida con GET /auth/me. Si el access expiró, el
 *    cliente HTTP lo renueva solo (refresh). Válido -> "authenticated"; si no -> "anonymous".
 *    Sin cookie CSRF -> "anonymous" al instante, sin ninguna petición.
 * 2. login(): POST /auth/login -> el backend fija las cookies -> "authenticated".
 * 3. logout(): POST /auth/logout (el SERVIDOR invalida la sesión) -> "anonymous".
 * 4. Si una renovación falla en cualquier petición -> "anonymous".
 *
 * SOLID — Inversión de dependencias: este componente NO importa authApi. Recibe
 * un `service` que cumple el puerto AuthService (ver types.ts). Quién lo crea
 * (HTTP real o demo) lo decide la raíz de composición: app/providers.tsx.
 */
import { type ReactNode, useCallback, useEffect, useMemo, useState } from 'react'

import { setUnauthorizedHandler } from '@/shared/api/client'
import { hasSessionHint } from '@/shared/api/csrf'

import { AuthContext } from './AuthContext'
import { userHasPermission } from './permissions'
import type {
  AuthContextValue,
  AuthService,
  AuthStatus,
  AuthUser,
  LoginCredentials,
  PasswordChange,
  Permission,
} from './types'

interface AuthState {
  readonly status: AuthStatus
  readonly user: AuthUser | null
}

const ANONYMOUS: AuthState = { status: 'anonymous', user: null } // objeto constante reutilizable

interface AuthProviderProps {
  readonly service: AuthService // dependencia INYECTADA (abstracción, no implementación)
  readonly children: ReactNode
}

export function AuthProvider({ service, children }: AuthProviderProps) {
  // Inicialización perezosa: se decide UNA vez, al montar, si hay que validar una sesión.
  const [state, setState] = useState<AuthState>(() =>
    hasSessionHint() ? { status: 'checking', user: null } : ANONYMOUS,
  )

  // Sesión perdida (la renovación falló): solo se limpia el estado local.
  const dropSession = useCallback(() => setState(ANONYMOUS), [])

  // Si el cliente axios no logra renovar la sesión, avisará aquí.
  useEffect(() => setUnauthorizedHandler(dropSession), [dropSession]) // devuelve la limpieza

  // Validación de la sesión existente (solo si status = "checking").
  const isChecking = state.status === 'checking'
  useEffect(() => {
    if (!isChecking) return
    let cancelled = false // evita actualizar estado si el componente se desmontó
    service
      .me()
      .then((user) => {
        if (!cancelled) setState({ status: 'authenticated', user })
      })
      .catch(() => {
        // Sesión inválida/expirada o backend caído: modo anónimo de forma segura.
        if (!cancelled) setState(ANONYMOUS)
      })
    return () => {
      cancelled = true // React StrictMode monta/desmonta dos veces en desarrollo
    }
  }, [isChecking, service])

  const login = useCallback(
    async (credentials: LoginCredentials) => {
      // Si falla, el ApiError se propaga al formulario de login para mostrar el mensaje.
      const user = await service.login(credentials)
      setState({ status: 'authenticated', user })
    },
    [service],
  )

  // logout NUNCA rechaza: salir debe funcionar siempre para el usuario. Si el servidor
  // no responde (sin red), la UI sale igual; la sesión del servidor caduca sola o se
  // revoca en el siguiente login/cambio de contraseña. Decisión documentada en el README.
  const logout = useCallback(async () => {
    await service.logout().catch(() => undefined) // el servidor revoca el refresh y borra cookies
    setState(ANONYMOUS)
  }, [service])

  const changePassword = useCallback(
    async (change: PasswordChange) => {
      // Si falla (contraseña actual mala, política...), el ApiError llega al formulario.
      const user = await service.changePassword(change)
      setState({ status: 'authenticated', user }) // mustChangePassword = false: se libera el panel
    },
    [service],
  )

  const hasPermission = useCallback(
    (permission: Permission) => userHasPermission(state.user, permission),
    [state.user],
  )

  // useMemo: el objeto del contexto solo cambia si cambia algo real -> menos renders.
  const value = useMemo<AuthContextValue>(
    () => ({ status: state.status, user: state.user, login, logout, changePassword, hasPermission }),
    [state, login, logout, changePassword, hasPermission],
  )

  return <AuthContext value={value}>{children}</AuthContext> // React 19: <Context> como proveedor
}
