/**
 * Layout PRIVADO del panel: menú lateral + barra superior + contenido.
 *
 * SOLID — Responsabilidad única: AppLayout solo ARMA la estructura. Delega:
 * - qué módulos mostrar   -> useVisibleNavigation (permisos)
 * - cómo pintar el menú   -> SidebarNav
 * - la sesión del usuario -> UserMenu
 * Se monta siempre dentro de <RequireAuth>, así que aquí ya hay sesión.
 */
import { Outlet } from 'react-router-dom'

import { IS_DEMO_AUTH } from '../authService'
import { Brand } from '../components/Brand'
import { APP_BASE_PATH } from '../navigation'
import { useVisibleNavigation } from '../useVisibleNavigation'
import './layouts.css'
import { SidebarNav } from './SidebarNav'
import { UserMenu } from './UserMenu'

export function AppLayout() {
  const items = useVisibleNavigation()

  return (
    <div className="app-shell">
      <a className="skip-link" href="#contenido">
        Saltar al contenido
      </a>

      <aside className="app-sidebar">
        <Brand to={APP_BASE_PATH} />
        <SidebarNav items={items} />
      </aside>

      <div className="app-body">
        <header className="app-topbar">
          {/* Aviso visible: en modo demo los datos de sesión son ficticios. */}
          {IS_DEMO_AUTH && (
            <span className="demo-flag" role="note">
              Modo demo · sesión simulada
            </span>
          )}
          <UserMenu />
        </header>
        <main id="contenido" className="app-main" tabIndex={-1}>
          <Outlet /> {/* aquí se pinta el módulo activo */}
        </main>
      </div>
    </div>
  )
}
