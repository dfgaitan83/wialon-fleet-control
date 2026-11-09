/**
 * Mapa de rutas de la aplicación (React Router).
 *
 *   /                 PublicLayout > LandingPage
 *   /login            PublicLayout > LoginPage
 *   /app/*            RequireAuth > AppLayout > [módulos de navigation.ts, cada uno con RequirePermission]
 *   *                 PublicLayout > NotFoundPage (404)
 *
 * Las rutas privadas NO se escriben a mano: se GENERAN desde APP_NAVIGATION
 * (Abierto/Cerrado: un módulo nuevo = una entrada en navigation.ts).
 * Se exporta `routes` para que los tests usen exactamente el mismo mapa.
 */
import { createBrowserRouter, type RouteObject } from 'react-router-dom'

import { ChangePasswordPage } from '@/features/auth/ChangePasswordPage'
import { LoginPage } from '@/features/auth/LoginPage'
import { LandingPage } from '@/features/landing/LandingPage'
import { VehicleDetailPage } from '@/features/vehicles/VehicleDetailPage'
import { RequireAuth } from '@/shared/auth/RequireAuth'
import { RequirePermission } from '@/shared/auth/RequirePermission'
import { CHANGE_PASSWORD_PATH, LOGIN_PATH } from '@/shared/auth/types'

import { AppLayout } from './layouts/AppLayout'
import { PublicLayout } from './layouts/PublicLayout'
import { APP_BASE_PATH, APP_NAVIGATION, type NavItem } from './navigation'
import { NotFoundPage } from './pages/NotFoundPage'
import { PendingModulePage } from './pages/PendingModulePage'
import { RouteErrorPage } from './pages/RouteErrorPage'

/** Convierte una entrada de navegación en ruta protegida por su permiso. */
function toModuleRoute(item: NavItem): RouteObject {
  const Page = item.page // página real si ya existe
  const element = (
    // Defensa en la UI: aunque se escriba la URL a mano, sin permiso no se ve el módulo.
    <RequirePermission permission={item.permission}>
      {Page ? <Page /> : <PendingModulePage title={item.label} milestone={item.milestone} />}
    </RequirePermission>
  )
  // segment "" = página índice de /app.
  return item.segment ? { path: item.segment, element } : { index: true, element }
}

export const routes: RouteObject[] = [
  {
    errorElement: <RouteErrorPage />, // captura errores de render de cualquier ruta hija
    children: [
      {
        element: <PublicLayout />,
        children: [
          { index: true, element: <LandingPage /> },
          { path: LOGIN_PATH, element: <LoginPage /> },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
      {
        path: APP_BASE_PATH,
        element: <RequireAuth />, // sin sesión -> /login (recordando a dónde se quería ir)
        children: [
          {
            element: <AppLayout />,
            children: [
              ...APP_NAVIGATION.map(toModuleRoute),
              {
                // RF-12: detalle (no es una entrada del menú, pero exige el mismo permiso)
                path: 'vehicles/:vehicleId',
                element: (
                  <RequirePermission permission="vehicles:read">
                    <VehicleDetailPage />
                  </RequirePermission>
                ),
              },
            ],
          },
        ],
      },
      {
        // RF-06: cambio de contraseña (obligatorio con contraseña temporal). Requiere sesión,
        // pero vive fuera del AppLayout: con contraseña temporal no se muestra el panel.
        path: CHANGE_PASSWORD_PATH,
        element: <RequireAuth />,
        children: [{ element: <PublicLayout />, children: [{ index: true, element: <ChangePasswordPage /> }] }],
      },
    ],
  },
]

/** Router del navegador (usa la URL real: /app/vehicles, etc.). */
export const router = createBrowserRouter(routes)
