/**
 * "Últimos reportes": los vehículos que reportaron más recientemente (señal viva
 * arriba). Datos del endpoint liviano de posiciones (el mismo del mapa).
 */
import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'

import { VehicleStatusBadge } from '@/features/vehicles/components/VehicleStatusBadge'
import type { MapPoint } from '@/features/vehicles/fleetApi'
import { formatDateTime, formatRelative, formatSpeed } from '@/shared/format'
import { EmptyState } from '@/shared/ui/EmptyState'

const LIMIT = 6

export function RecentReports({ points }: { readonly points: readonly MapPoint[] }) {
  const recent = [...points].sort((a, b) => b.recordedAt.getTime() - a.recordedAt.getTime()).slice(0, LIMIT)

  if (recent.length === 0) {
    return <EmptyState title="Sin reportes" description="Ningún vehículo ha enviado posición todavía." />
  }

  return (
    <ol className="recent">
      {recent.map((point, index) => (
        <li key={point.id} className="recent__item" style={{ '--i': index } as CSSProperties}>
          <Link to={`/app/vehicles/${point.id}`} className="recent__name">
            {point.name}
          </Link>
          <VehicleStatusBadge status={point.status} />
          <span className="recent__meta">
            {formatSpeed(point.speedKmh)} ·{' '}
            <time dateTime={point.recordedAt.toISOString()} title={formatDateTime(point.recordedAt)}>
              {formatRelative(point.recordedAt)}
            </time>
          </span>
        </li>
      ))}
    </ol>
  )
}
