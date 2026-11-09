/**
 * Layout PÚBLICO (landing, login): cabecera con marca, contenido y pie.
 * Responsabilidad única: la estructura de las páginas públicas. No pide datos.
 */
import { Outlet, useLocation } from 'react-router-dom'

import { LOGIN_PATH } from '@/shared/auth/types'
import { useAuth } from '@/shared/auth/useAuth'
import { ButtonLink } from '@/shared/ui/ButtonLink'

import { Brand } from '../components/Brand'
import { APP_BASE_PATH } from '../navigation'
import './layouts.css'

export function PublicLayout() {
  const { status } = useAuth()
  const { pathname } = useLocation()
  const isAuthenticated = status === 'authenticated'
  const isOnLogin = pathname === LOGIN_PATH // en /login el botón "Ingresar" sería redundante

  return (
    <div className="public-shell">
      <a className="skip-link" href="#contenido">
        Saltar al contenido
      </a>
      <header className="public-header">
        <Brand to="/" />
        {!isOnLogin && (
        <nav aria-label="Acceso">
          {/* Si ya hay sesión no tiene sentido "Ingresar": se ofrece volver al panel. */}
          <ButtonLink variant="primary" to={isAuthenticated ? APP_BASE_PATH : LOGIN_PATH}>
            {isAuthenticated ? 'Ir al panel' : 'Ingresar'}
          </ButtonLink>
        </nav>
        )}
      </header>

      <main id="contenido" className="public-main" tabIndex={-1}>
        <Outlet /> {/* aquí se pinta la página pública activa */}
      </main>

      <footer className="public-footer">
        <p>© {new Date().getFullYear()} Fleet Control · Monitoreo de flota sobre Wialon</p>
      </footer>
    </div>
  )
}
