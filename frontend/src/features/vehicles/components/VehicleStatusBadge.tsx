/**
 * Badge de estado de un vehículo: <VehicleStatusBadge status="moving" />
 * Reutiliza el StatusBadge genérico de shared/ui (sin duplicar estilos ni markup).
 */
import { StatusBadge } from '@/shared/ui'

import { VEHICLE_STATUS_PRESENTATION, type VehicleStatus } from '../vehicleStatus'

interface VehicleStatusBadgeProps {
  readonly status: VehicleStatus
  readonly title?: string // ej. "Último reporte: 2026-11-08 04:55 (hora Bogotá)"
}

export function VehicleStatusBadge({ status, title }: VehicleStatusBadgeProps) {
  const { label, tone, pulse } = VEHICLE_STATUS_PRESENTATION[status]
  return <StatusBadge tone={tone} label={label} pulse={pulse} title={title} />
}
