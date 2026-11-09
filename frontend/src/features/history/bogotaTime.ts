/**
 * Conversión entre <input type="datetime-local"> y Date en hora de Bogotá.
 * Bogotá es UTC-5 todo el año (sin horario de verano), así que el desfase es fijo:
 * el input se interpreta SIEMPRE en hora de Bogotá, sin importar la zona del navegador.
 */
const BOGOTA_OFFSET = '-05:00'
const BOGOTA_OFFSET_MS = 5 * 60 * 60 * 1000

/** "2026-11-08T07:30" (hora Bogotá) -> Date. Devuelve null si el texto no es válido. */
export function bogotaInputToDate(value: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) return null
  const date = new Date(`${value}:00${BOGOTA_OFFSET}`)
  return Number.isNaN(date.getTime()) ? null : date
}

/** Date -> "2026-11-08T07:30" en hora de Bogotá (valor para el input). */
export function dateToBogotaInput(date: Date): string {
  return new Date(date.getTime() - BOGOTA_OFFSET_MS).toISOString().slice(0, 16)
}
