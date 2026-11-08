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

import { LOGIN_PATH } from './types'
import { useAuth } from './useAuth'

interface RequireAuthProps {
  readonly children?: ReactNode // opcional: si no se pasa, se renderizan las rutas hijas (<Outlet/>)
}

export function RequireAuth({ children }: RequireAuthProps) {
  const { status } = useAuth()
  const location = useLocation()

  // Mientras se valida el token tras un F5, no redirigir (evita "parpadeo" hacia /login).
  if (status === 'checking') {
    return (
      <p role="status" aria-live="polite" className="ui-page-status">
        Verificando sesión…
      </p>
    )
  }

  if (status === 'anonymous') {
    // replace: el /login no queda en el historial (el botón "atrás" no vuelve a la ruta protegida).
    // state.from: tras el login se puede volver a la página que se intentaba abrir.
    return <Navigate to={LOGIN_PATH} replace state={{ from: location }} />
  }

  return children ?? <Outlet />
}
