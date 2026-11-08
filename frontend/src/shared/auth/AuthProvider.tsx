/**
 * Proveedor de sesión: guarda quién está logueado y lo comparte con toda la app.
 *
 * Ciclo de vida:
 * 1. Al cargar la app: si hay token guardado (tras un F5) -> status "checking" y se
 *    valida con GET /auth/me. Si es válido -> "authenticated"; si no -> "anonymous".
 * 2. login(): POST /auth/login -> guarda token -> "authenticated".
 * 3. logout() o cualquier 401 del backend -> borra token -> "anonymous".
 *
 * SOLID — Inversión de dependencias: este componente NO importa authApi. Recibe
 * un `service` que cumple el puerto AuthService (ver types.ts). Quién lo crea
 * (HTTP real o demo) lo decide la raíz de composición: app/providers.tsx.
 */
import { type ReactNode, useCallback, useEffect, useMemo, useState } from 'react'

import { setUnauthorizedHandler } from '@/shared/api/client'

import { AuthContext } from './AuthContext'
import { userHasPermission } from './permissions'
import { tokenStorage } from './tokenStorage'
import type {
  AuthContextValue,
  AuthService,
  AuthStatus,
  AuthUser,
  LoginCredentials,
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
  // Inicialización perezosa: se decide UNA vez, al montar, si hay que validar un token.
  const [state, setState] = useState<AuthState>(() =>
    tokenStorage.get() ? { status: 'checking', user: null } : ANONYMOUS,
  )

  // logout estable (useCallback): se registra como handler del 401 y no cambia entre renders.
  const logout = useCallback(() => {
    tokenStorage.clear() // 1) olvidar el token
    setState(ANONYMOUS) // 2) la UI pasa a modo anónimo -> RequireAuth redirige a /login
  }, [])

  // Al recibir un 401 en cualquier petición, el cliente axios llamará a logout.
  useEffect(() => setUnauthorizedHandler(logout), [logout]) // devuelve la función de limpieza

  // Validación del token guardado (solo si status = "checking").
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
        // Token inválido/expirado o backend caído: sesión cerrada de forma segura.
        if (!cancelled) logout()
      })
    return () => {
      cancelled = true // React StrictMode monta/desmonta dos veces en desarrollo
    }
  }, [isChecking, logout, service])

  const login = useCallback(
    async (credentials: LoginCredentials) => {
      // Si falla, el ApiError se propaga al formulario de login para mostrar el mensaje.
      const { accessToken, user } = await service.login(credentials)
      tokenStorage.set(accessToken)
      setState({ status: 'authenticated', user })
    },
    [service],
  )

  const hasPermission = useCallback(
    (permission: Permission) => userHasPermission(state.user, permission),
    [state.user],
  )

  // useMemo: el objeto del contexto solo cambia si cambia algo real -> menos renders.
  const value = useMemo<AuthContextValue>(
    () => ({ status: state.status, user: state.user, login, logout, hasPermission }),
    [state, login, logout, hasPermission],
  )

  return <AuthContext value={value}>{children}</AuthContext> // React 19: <Context> como proveedor
}
