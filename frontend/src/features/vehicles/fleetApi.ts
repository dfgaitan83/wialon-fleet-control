/**
 * Acceso a la API de flota (vehículos, posiciones, detalle, KPIs) con contratos zod.
 * Backend: backend/app/api/v1/fleet.py. Fechas ISO-8601 UTC -> Date; el formato
 * en hora de Bogotá lo hace shared/format.ts al pintar.
 */
import { z } from 'zod'

import { apiClient } from '@/shared/api/client'
import { ApiError } from '@/shared/api/problem'

import type { VehicleStatus } from './vehicleStatus'

const statusSchema = z.enum(['moving', 'stopped', 'offline'])
const dateSchema = z.iso.datetime({ offset: true }).transform((value) => new Date(value))

const positionSchema = z.object({
  latitude: z.number(),
  longitude: z.number(),
  speed_kmh: z.number(),
  heading_deg: z.number(),
  recorded_at: dateSchema,
  altitude_m: z.number().nullable(),
  satellites: z.number(),
})
const driverSchema = z.object({
  id: z.number(),
  resource_id: z.number(),
  name: z.string(),
  code: z.string(),
  phone: z.string(),
})
const passengerSchema = z.object({ id: z.number(), resource_id: z.number(), name: z.string(), code: z.string() })
const customFieldSchema = z.object({ id: z.number(), name: z.string(), value: z.string() })

const vehicleSchema = z.object({
  id: z.number(),
  name: z.string(),
  status: statusSchema,
  position: positionSchema.nullable(),
  driver: driverSchema.nullable(),
  passenger_count: z.number(),
})
const detailSchema = vehicleSchema.extend({
  passengers: z.array(passengerSchema),
  custom_fields: z.array(customFieldSchema),
})
const pageSchema = z.object({
  items: z.array(vehicleSchema),
  total: z.number(),
  page: z.number(),
  page_size: z.number(),
})
const mapPointSchema = z.object({
  id: z.number(),
  name: z.string(),
  status: statusSchema,
  latitude: z.number(),
  longitude: z.number(),
  speed_kmh: z.number(),
  heading_deg: z.number(),
  recorded_at: dateSchema,
  driver_name: z.string().nullable(),
})
const summarySchema = z.object({
  total_vehicles: z.number(),
  by_status: z.array(z.object({ status: statusSchema, count: z.number() })),
  with_driver: z.number(),
  without_driver: z.number(),
  total_drivers: z.number(),
  total_passengers: z.number(),
  generated_at: dateSchema,
})

export interface Position {
  readonly latitude: number
  readonly longitude: number
  readonly speedKmh: number
  readonly headingDeg: number
  readonly recordedAt: Date
}
export interface Driver {
  readonly id: number
  readonly resourceId: number
  readonly name: string
  readonly code: string
  readonly phone: string
}
export interface VehicleSummary {
  readonly id: number
  readonly name: string
  readonly status: VehicleStatus
  readonly position: Position | null
  readonly driver: Driver | null
  readonly passengerCount: number
}
export interface VehicleDetail extends VehicleSummary {
  readonly passengers: ReadonlyArray<{ id: number; name: string; code: string }>
  readonly customFields: ReadonlyArray<{ id: number; name: string; value: string }>
}
export interface MapPoint {
  readonly id: number
  readonly name: string
  readonly status: VehicleStatus
  readonly latitude: number
  readonly longitude: number
  readonly speedKmh: number
  readonly headingDeg: number
  readonly recordedAt: Date
  readonly driverName: string | null
}
export interface FleetSummary {
  readonly totalVehicles: number
  readonly byStatus: Readonly<Record<'moving' | 'stopped' | 'offline', number>>
  readonly withDriver: number
  readonly withoutDriver: number
  readonly totalDrivers: number
  readonly totalPassengers: number
  readonly generatedAt: Date
}

function parse<T>(schema: z.ZodType<T>, data: unknown): T {
  const result = schema.safeParse(data)
  if (!result.success) throw new ApiError(502, 'El servidor respondió en un formato inesperado.')
  return result.data
}

const toPosition = (p: z.infer<typeof positionSchema> | null): Position | null =>
  p && { latitude: p.latitude, longitude: p.longitude, speedKmh: p.speed_kmh, headingDeg: p.heading_deg, recordedAt: p.recorded_at }

const toDriver = (d: z.infer<typeof driverSchema> | null): Driver | null =>
  d && { id: d.id, resourceId: d.resource_id, name: d.name, code: d.code, phone: d.phone }

function toVehicle(v: z.infer<typeof vehicleSchema>): VehicleSummary {
  return {
    id: v.id,
    name: v.name,
    status: v.status,
    position: toPosition(v.position),
    driver: toDriver(v.driver),
    passengerCount: v.passenger_count,
  }
}

export interface VehicleQuery {
  readonly page: number
  readonly pageSize: number
  readonly search: string
  readonly status: VehicleStatus | ''
}

export const fleetApi = {
  async vehicles(query: VehicleQuery) {
    const { data } = await apiClient.get<unknown>('/vehicles', {
      params: {
        page: query.page,
        page_size: query.pageSize,
        q: query.search || undefined,
        status: query.status || undefined,
      },
    })
    const page = parse(pageSchema, data)
    return { items: page.items.map(toVehicle), total: page.total, page: page.page, pageSize: page.page_size }
  },

  async positions(): Promise<MapPoint[]> {
    const { data } = await apiClient.get<unknown>('/vehicles/positions')
    return parse(z.array(mapPointSchema), data).map((p) => ({
      id: p.id,
      name: p.name,
      status: p.status,
      latitude: p.latitude,
      longitude: p.longitude,
      speedKmh: p.speed_kmh,
      headingDeg: p.heading_deg,
      recordedAt: p.recorded_at,
      driverName: p.driver_name,
    }))
  },

  async vehicle(id: number): Promise<VehicleDetail> {
    const { data } = await apiClient.get<unknown>(`/vehicles/${id}`)
    const v = parse(detailSchema, data)
    return {
      ...toVehicle(v),
      passengers: v.passengers.map(({ id: pid, name, code }) => ({ id: pid, name, code })),
      customFields: v.custom_fields,
    }
  },

  async summary(): Promise<FleetSummary> {
    const { data } = await apiClient.get<unknown>('/dashboard/summary')
    const s = parse(summarySchema, data)
    const byStatus = { moving: 0, stopped: 0, offline: 0 }
    for (const item of s.by_status) byStatus[item.status] = item.count
    return {
      totalVehicles: s.total_vehicles,
      byStatus,
      withDriver: s.with_driver,
      withoutDriver: s.without_driver,
      totalDrivers: s.total_drivers,
      totalPassengers: s.total_passengers,
      generatedAt: s.generated_at,
    }
  },
}

export const fleetKeys = {
  all: ['fleet'] as const,
  vehicles: (q: VehicleQuery) => ['fleet', 'vehicles', q] as const,
  positions: ['fleet', 'positions'] as const,
  vehicle: (id: number) => ['fleet', 'vehicle', id] as const,
  summary: ['fleet', 'summary'] as const,
}

/** RF-14: refresco de posiciones cada 15 s (TanStack lo PAUSA con la pestaña oculta). */
export const POSITIONS_REFRESH_MS = 15_000
