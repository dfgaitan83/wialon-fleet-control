/**
 * Historial de recorridos (RF-24). Backend: GET /api/v1/vehicles/{id}/track?from&to.
 * Las estadísticas (distancia, velocidad máx.) vienen calculadas del backend.
 */
import { z } from 'zod'

import { apiClient } from '@/shared/api/client'
import { ApiError } from '@/shared/api/problem'

const dateSchema = z.iso.datetime({ offset: true }).transform((value) => new Date(value))

const trackSchema = z.object({
  vehicle_id: z.number(),
  start: dateSchema,
  end: dateSchema,
  total_points: z.number(),
  distance_km: z.number(),
  max_speed_kmh: z.number(),
  moving_minutes: z.number(),
  points: z.array(
    z.object({
      latitude: z.number(),
      longitude: z.number(),
      speed_kmh: z.number(),
      heading_deg: z.number(),
      recorded_at: dateSchema,
    }),
  ),
})

export interface TrackPoint {
  readonly latitude: number
  readonly longitude: number
  readonly speedKmh: number
  readonly headingDeg: number
  readonly recordedAt: Date
}

export interface Track {
  readonly vehicleId: number
  readonly totalPoints: number
  readonly distanceKm: number
  readonly maxSpeedKmh: number
  readonly movingMinutes: number
  readonly points: readonly TrackPoint[]
}

export interface TrackQuery {
  readonly vehicleId: number
  readonly from: Date
  readonly to: Date
}

export const historyKeys = {
  track: (q: TrackQuery) => ['history', q.vehicleId, q.from.toISOString(), q.to.toISOString()] as const,
}

export const historyApi = {
  async track(q: TrackQuery): Promise<Track> {
    const { data } = await apiClient.get<unknown>(`/vehicles/${q.vehicleId}/track`, {
      params: { from: q.from.toISOString(), to: q.to.toISOString() },
    })
    const parsed = trackSchema.safeParse(data)
    if (!parsed.success) throw new ApiError(502, 'El servidor respondió en un formato inesperado.')
    const t = parsed.data
    return {
      vehicleId: t.vehicle_id,
      totalPoints: t.total_points,
      distanceKm: t.distance_km,
      maxSpeedKmh: t.max_speed_kmh,
      movingMinutes: t.moving_minutes,
      points: t.points.map((p) => ({
        latitude: p.latitude,
        longitude: p.longitude,
        speedKmh: p.speed_kmh,
        headingDeg: p.heading_deg,
        recordedAt: p.recorded_at,
      })),
    }
  },
}
