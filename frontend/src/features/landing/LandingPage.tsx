/**
 * Landing pública (versión base). La landing completa (propuesta de valor,
 * funcionalidades, cómo funciona, CTA) se construye en la meta M6.
 */
import { LOGIN_PATH } from '@/shared/auth/types'
import { ButtonLink } from '@/shared/ui/ButtonLink'
import { StatusBadge } from '@/shared/ui/StatusBadge'
import '@/shared/ui/styles/components.css' // primitivas page-eyebrow / page-card

import './landing.css'

export function LandingPage() {
  return (
    <section className="landing-hero" aria-labelledby="hero-title">
      <div className="landing-hero__copy">
        <p className="page-eyebrow">Monitoreo de flota en tiempo real</p>
        <h1 id="hero-title" className="landing-hero__title">
          Tu flota, <span className="landing-hero__accent">en una sola vista.</span>
        </h1>
        <p className="landing-hero__lead">
          Ubicación, estado, conductores y pasajeros de cada vehículo, sincronizados con Wialon y con
          permisos por rol para tu equipo.
        </p>
        <div className="landing-hero__actions">
          <ButtonLink to={LOGIN_PATH} variant="primary">
            Ingresar al panel
          </ButtonLink>
        </div>
      </div>

      {/* Vista previa ilustrativa del estado de la flota (decorativa: datos de ejemplo). */}
      <aside className="landing-preview page-card" aria-label="Ejemplo de estados de vehículos">
        <p className="landing-preview__title">Estado de la flota</p>
        <ul className="landing-preview__list">
          <li>
            <span className="landing-preview__plate">FSU778</span>
            <StatusBadge tone="success" label="En movimiento" pulse />
          </li>
          <li>
            <span className="landing-preview__plate">GUV875</span>
            <StatusBadge tone="warning" label="Detenido" />
          </li>
          <li>
            <span className="landing-preview__plate">LLO843</span>
            <StatusBadge tone="neutral" label="Sin conexión" />
          </li>
        </ul>
      </aside>
    </section>
  )
}
