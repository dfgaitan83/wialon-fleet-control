/**
 * Estados de vehículo que muestra la UI y cómo se presenta cada uno.
 *
 * El estado lo CALCULA el backend (regla de dominio en app/domain/status.py, a
 * partir de velocidad y antigüedad del último reporte de Wialon). El frontend
 * solo lo traduce a texto y color: no repite la regla de negocio.
 */
import type { StatusTone } from '@/shared/ui'

/** Estados posibles (string union en vez de enum: más simple y sin código generado). */
export type VehicleStatus = 'moving' | 'stopped' | 'offline' | 'unknown'

interface StatusPresentation {
  readonly label: string // texto en español
  readonly tone: StatusTone // color semántico
  readonly pulse: boolean // ¿señal "viva"?
}

// Record<VehicleStatus, ...>: si mañana se añade un estado, TypeScript obliga a
// definir aquí su presentación (no puede quedar un estado sin texto).
export const VEHICLE_STATUS_PRESENTATION: Readonly<Record<VehicleStatus, StatusPresentation>> = {
  moving: { label: 'En movimiento', tone: 'success', pulse: true },
  stopped: { label: 'Detenido', tone: 'warning', pulse: false },
  offline: { label: 'Sin conexión', tone: 'neutral', pulse: false },
  unknown: { label: 'Sin datos', tone: 'info', pulse: false }, // ej. unidad que nunca reportó posición
}
