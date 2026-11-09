/**
 * Formato para el usuario (sección 4.4): la API entrega UTC; la UI muestra hora de
 * Bogotá (America/Bogota), velocidad en km/h y rumbo como punto cardinal.
 */
const TIME_ZONE = 'America/Bogota'

const dateTimeFormat = new Intl.DateTimeFormat('es-CO', {
  timeZone: TIME_ZONE,
  dateStyle: 'medium',
  timeStyle: 'short',
})

/** "8 nov 2026, 10:13 p. m." en hora de Bogotá. */
export function formatDateTime(date: Date): string {
  return dateTimeFormat.format(date)
}

const relative = new Intl.RelativeTimeFormat('es-CO', { numeric: 'auto' })

/** "hace 5 minutos", "hace 2 días"... (para "último reporte"). */
export function formatRelative(date: Date, now: Date = new Date()): string {
  const seconds = Math.round((date.getTime() - now.getTime()) / 1000)
  const steps: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ['day', 86_400],
    ['hour', 3_600],
    ['minute', 60],
  ]
  for (const [unit, size] of steps) {
    if (Math.abs(seconds) >= size) return relative.format(Math.round(seconds / size), unit)
  }
  return relative.format(seconds, 'second')
}

const CARDINALS = ['N', 'NE', 'E', 'SE', 'S', 'SO', 'O', 'NO'] as const

/** Rumbo en grados -> punto cardinal en español (0 = N, 90 = E, 225 = SO). */
export function toCardinal(degrees: number): (typeof CARDINALS)[number] {
  const normalized = ((degrees % 360) + 360) % 360
  return CARDINALS[Math.round(normalized / 45) % CARDINALS.length]
}

const speedFormat = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 })

export function formatSpeed(kmh: number): string {
  return `${speedFormat.format(kmh)} km/h`
}
