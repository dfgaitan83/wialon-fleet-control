/**
 * Guardia de ruta: solo deja pasar a usuarios autenticados.
 *
 * Uso en el router (paso 2):
 *   <Route element={<RequireAuth />}>
 *     <Route path="/vehicles" element={<VehiclesPage />} />
 *   </Route>
 */
import type { ReactNode } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { ServerWakeNotice } from '@/shared/server/ServerWakeNotice'

import { CHANGE_PASSWORD_PATH, LOGIN_PATH } from './types'
import { useAuth } from './useAuth'

interface RequireAuthProps {
  readonly children?: ReactNode // opcional: si no se pasa, se renderizan las rutas hijas (<Outlet/>)
}

export function RequireAuth({ children }: RequireAuthProps) {
  const { status, user } = useAuth()
  const location = useLocation()

  // Mientras se valida el token tras un F5, no redirigir (evita "parpadeo" hacia /login).
  if (status === 'checking') {
    return (
      <div className="ui-page-status">
        <p role="status" aria-live="polite">
          Verificando sesión…
        </p>
        <ServerWakeNotice /> {/* DEP-04: si el servidor está dormido, se explica la espera */}
      </div>
    )
  }

  if (status === 'anonymous') {
    // replace: el /login no queda en el historial (el botón "atrás" no vuelve a la ruta protegida).
    // state.from: tras el login se puede volver a la página que se intentaba abrir.
    return <Navigate to={LOGIN_PATH} replace state={{ from: location }} />
  }

  // RF-06: con contraseña temporal, la ÚNICA pantalla accesible es la de cambiarla
  // (el backend además responde 403 a todo lo demás: doble capa).
  if (user?.mustChangePassword && location.pathname !== CHANGE_PASSWORD_PATH) {
    return <Navigate to={CHANGE_PASSWORD_PATH} replace />
  }

  return children ?? <Outlet />
}
