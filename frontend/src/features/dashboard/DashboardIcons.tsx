/**
 * Íconos SVG del dashboard: misma familia visual que el menú (trazo 1.8, extremos
 * redondeados, 24x24). Decorativos (aria-hidden): el texto de la tarjeta ya informa.
 */
import type { ReactNode } from 'react'

function Icon({ children }: { readonly children: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  )
}

export const FleetIcon = () => (
  <Icon>
    <rect x="3" y="6" width="13" height="10" rx="2" />
    <path d="M16 9h3l2 3v4h-5" />
    <circle cx="7" cy="17.5" r="1.8" />
    <circle cx="17" cy="17.5" r="1.8" />
  </Icon>
)

export const MovingIcon = () => (
  <Icon>
    <path d="M3 17h4l3-8 4 12 3-7h4" />
  </Icon>
)

export const StoppedIcon = () => (
  <Icon>
    <circle cx="12" cy="12" r="9" />
    <path d="M9.5 9v6M14.5 9v6" />
  </Icon>
)

export const OfflineIcon = () => (
  <Icon>
    <path d="M2 8.8a15 15 0 0 1 4.2-2.5M9.5 5.2A15 15 0 0 1 22 8.8M5 12.5a10 10 0 0 1 3-1.8M14 10.6a10 10 0 0 1 5 1.9M8.5 16.1a5 5 0 0 1 7 0" />
    <path d="M3 3l18 18" />
    <circle cx="12" cy="19.5" r="0.8" />
  </Icon>
)

export const DriverIcon = () => (
  <Icon>
    <circle cx="12" cy="8" r="3.5" />
    <path d="M5 20a7 7 0 0 1 14 0" />
  </Icon>
)

export const PassengersIcon = () => (
  <Icon>
    <circle cx="9" cy="8.5" r="3" />
    <path d="M3.5 19a5.5 5.5 0 0 1 11 0" />
    <circle cx="17" cy="9.5" r="2.4" />
    <path d="M16 14.2a4.5 4.5 0 0 1 5 4.8" />
  </Icon>
)
