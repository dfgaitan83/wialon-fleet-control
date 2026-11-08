/**
 * Marca de la aplicación (isotipo + nombre). La usan PublicLayout y AppLayout.
 * Isotipo: marcador de ubicación con ondas de señal (GPS) en el rojo de marca #EB162C.
 */
import { Link } from 'react-router-dom'

interface BrandProps {
  readonly to: string // a dónde lleva el clic en la marca
  readonly tone?: 'default' | 'inverse' // inverse: sobre fondos oscuros
}

export function BrandMark() {
  return (
    <svg width="32" height="32" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <rect width="32" height="32" rx="9" fill="var(--color-brand)" />
      {/* Marcador de posición */}
      <path d="M16 25s-6-5.6-6-10.2a6 6 0 1 1 12 0C22 19.4 16 25 16 25z" fill="#fff" />
      <circle cx="16" cy="14.6" r="2.3" fill="var(--color-brand)" />
      {/* Onda de señal (teal = "señal viva", el mismo color de "en movimiento") */}
      <path d="M23.5 7.5a9 9 0 0 1 2.2 4" stroke="var(--palette-teal)" strokeWidth="2" strokeLinecap="round" fill="none" />
    </svg>
  )
}

export function Brand({ to, tone = 'default' }: BrandProps) {
  return (
    <Link to={to} className={`brand brand--${tone}`} aria-label="Wialon Fleet Control, inicio">
      <BrandMark />
      <span className="brand__name">
        Fleet<span className="brand__accent">Control</span>
      </span>
    </Link>
  )
}
