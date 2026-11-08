/**
 * Insignia de estado GENÉRICA (punto de color + texto).
 *
 * <StatusBadge tone="success" label="En movimiento" pulse />
 *
 * ¿Por qué genérica y no "de vehículos"? shared/ui no debe conocer conceptos de
 * negocio (qué es "detenido"). El mapeo estado-de-vehículo -> tono vive en
 * features/vehicles/components/VehicleStatusBadge.tsx. Así este badge sirve
 * también para usuarios (activo/inactivo), auditoría, etc.
 *
 * Accesibilidad: el color NUNCA es el único portador del significado; siempre
 * hay texto (personas daltónicas o lectores de pantalla).
 */
import { cx } from './cx'
import './styles/components.css'

export type StatusTone = 'success' | 'warning' | 'danger' | 'neutral' | 'info'

interface StatusBadgeProps {
  readonly tone: StatusTone
  readonly label: string // texto visible y leído por lectores de pantalla
  readonly pulse?: boolean // animación de "señal viva" (respeta prefers-reduced-motion)
  readonly title?: string // tooltip opcional con más detalle (ej. "Último reporte hace 3 min")
}

export function StatusBadge({ tone, label, pulse = false, title }: StatusBadgeProps) {
  return (
    <span
      className={cx('ui-badge', tone !== 'neutral' && `ui-badge--${tone}`, pulse && 'ui-badge--pulse')}
      title={title}
    >
      <span className="ui-badge__dot" aria-hidden="true" /> {/* decorativo: el texto ya informa */}
      {label}
    </span>
  )
}
