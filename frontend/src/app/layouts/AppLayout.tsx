/**
 * Layout PRIVADO del panel: menú lateral + barra superior + contenido.
 *
 * SOLID — Responsabilidad única: AppLayout solo ARMA la estructura. Delega:
 * - qué módulos mostrar   -> useVisibleNavigation (permisos)
 * - cómo pintar el menú   -> SidebarNav
 * - la sesión del usuario -> UserMenu
 * Se monta siempre dentro de <RequireAuth>, así que aquí ya hay sesión.
 *
 * Móvil (< 900 px): el menú se abre con un botón "Menú" (patrón disclosure:
 * aria-expanded + aria-controls) y muestra TODAS las opciones en vertical. Antes
 * era una franja con scroll horizontal donde solo se veía "Resumen": parecía roto.
 * Se cierra al elegir una opción o con Escape. En escritorio es el menú lateral fijo.
 */
import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'

import { IS_DEMO_AUTH } from '../authService'
import { Brand } from '../components/Brand'
import { APP_BASE_PATH, navItemPath } from '../navigation'
import { useVisibleNavigation } from '../useVisibleNavigation'
import './layouts.css'
import { SidebarNav } from './SidebarNav'
import { UserMenu } from './UserMenu'

const NAV_ID = 'menu-principal'

function MenuIcon({ open }: { readonly open: boolean }) {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      {open ? <path d="M6 6l12 12M18 6 6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
    </svg>
  )
}

export function AppLayout() {
  const items = useVisibleNavigation()
  const { pathname } = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)

  // Sección actual (para que el botón diga dónde estás): la entrada más específica que coincide.
  const current = [...items]
    .sort((a, b) => navItemPath(b).length - navItemPath(a).length)
    .find((item) => pathname === navItemPath(item) || pathname.startsWith(`${navItemPath(item)}/`))

  // Escape cierra el menú móvil (UX: escape-routes).
  useEffect(() => {
    if (!menuOpen) return
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && setMenuOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [menuOpen])

  return (
    <div className="app-shell">
      <a className="skip-link" href="#contenido">
        Saltar al contenido
      </a>

      {menuOpen && (
        <div
          className="menu-backdrop"
          aria-hidden="true"
          onClick={() => setMenuOpen(false)}
        />
      )}
      <aside className="app-sidebar" data-menu-open={menuOpen}>
        <Brand to={APP_BASE_PATH} />
        <button
          type="button"
          className="app-menu-toggle"
          aria-expanded={menuOpen}
          aria-controls={NAV_ID}
          onClick={() => setMenuOpen((open) => !open)}
        >
          <MenuIcon open={menuOpen} />
          <span>
            Menú{current && <span className="app-menu-toggle__current"> · {current.label}</span>}
          </span>
        </button>
        <SidebarNav id={NAV_ID} items={items} onNavigate={() => setMenuOpen(false)} />
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
