/**
 * Marco visual de las pantallas de acceso (login y cambio de contraseña).
 *
 * Pantalla dividida: a la izquierda el panel de marca (qué es el producto y por qué
 * importa), a la derecha el formulario. En móvil el panel se reduce a una franja.
 * El trazado de ruta es SVG decorativo (aria-hidden): no aporta información.
 */
import type { ReactNode } from 'react'

import './auth.css'

interface AuthShellProps {
  readonly eyebrow: string
  readonly title: string
  readonly titleId: string
  readonly subtitle: string
  readonly children: ReactNode
}

const BENEFITS = [
  { title: 'Posición en vivo', text: 'Mapa actualizado cada 15 segundos.' },
  { title: 'Conductores y pasajeros', text: 'Asignaciones sincronizadas con Wialon.' },
  { title: 'Acceso por roles', text: 'Cada persona ve solo lo que necesita.' },
] as const

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m5 12 4.5 4.5L19 7" />
    </svg>
  )
}

/** Ruta GPS estilizada: polilínea con paradas (textura de marca, sin datos reales). */
function RouteArt() {
  return (
    <svg className="auth-brand__art" viewBox="0 0 400 300" aria-hidden="true" preserveAspectRatio="xMidYMid slice">
      <path
        className="auth-brand__route"
        d="M-10 250 C 60 230, 70 160, 140 170 S 230 240, 280 180 S 340 60, 420 70"
      />
      <path className="auth-brand__route auth-brand__route--faint" d="M-10 120 C 80 140, 120 60, 200 80 S 320 160, 420 130" />
      {[
        [140, 170],
        [280, 180],
        [372, 66],
      ].map(([cx, cy]) => (
        <g key={`${cx}-${cy}`}>
          <circle className="auth-brand__halo" cx={cx} cy={cy} r="14" />
          <circle className="auth-brand__stop" cx={cx} cy={cy} r="5" />
        </g>
      ))}
    </svg>
  )
}

export function AuthShell({ eyebrow, title, titleId, subtitle, children }: AuthShellProps) {
  return (
    <section className="auth" aria-labelledby={titleId}>
      <aside className="auth-brand">
        <RouteArt />
        <div className="auth-brand__content">
          <p className="auth-brand__eyebrow">Fleet Control</p>
          <p className="auth-brand__headline">Tu flota, en tiempo real.</p>
          <ul className="auth-brand__benefits">
            {BENEFITS.map((benefit) => (
              <li key={benefit.title}>
                <span className="auth-brand__check">
                  <CheckIcon />
                </span>
                <span>
                  <strong>{benefit.title}</strong>
                  <span className="auth-brand__benefit-text">{benefit.text}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      <div className="auth-panel">
        <header className="auth-panel__header">
          <p className="page-eyebrow">{eyebrow}</p>
          <h1 id={titleId} className="auth-panel__title">
            {title}
          </h1>
          <p className="auth-panel__subtitle">{subtitle}</p>
        </header>
        {children}
      </div>
    </section>
  )
}
