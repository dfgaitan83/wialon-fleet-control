/**
 * API de conductores y pasajeros (RF-08, RF-09, RF-16..18, RF-27, RF-28), contratos zod.
 * Un solo cliente para los dos tipos: mismo contrato, distinto prefijo.
 * Backend: backend/app/api/v1/people.py.
 */
import { z } from 'zod'

import { apiClient } from '@/shared/api/client'
import { ApiError } from '@/shared/api/problem'
import type { Permission } from '@/shared/auth/types'

export type PersonKind = 'drivers' | 'passengers'

export const KIND_TEXT: Readonly<
  Record<PersonKind, { singular: string; plural: string; read: Permission; write: Permission; hasPhone: boolean }>
> = {
  drivers: { singular: 'conductor', plural: 'Conductores', read: 'drivers:read', write: 'drivers:write', hasPhone: true },
  passengers: { singular: 'pasajero', plural: 'Pasajeros', read: 'passengers:read', write: 'passengers:write', hasPhone: true },
}

const personSchema = z.object({
  id: z.number(),
  resource_id: z.number(),
  name: z.string(),
  code: z.string(),
  description: z.string(),
  phone: z.string(),
  custom_fields: z.record(z.string(), z.string()),
  vehicle: z.object({ id: z.number(), name: z.string() }).nullable(),
})
const pageSchema = z.object({ items: z.array(personSchema), total: z.number(), page: z.number(), page_size: z.number() })

export interface Person {
  readonly id: number
  readonly resourceId: number
  readonly name: string
  readonly code: string
  readonly description: string
  readonly phone: string
  readonly customFields: Readonly<Record<string, string>>
  readonly vehicle: { readonly id: number; readonly name: string } | null
}

export interface PersonInput {
  readonly name: string
  readonly code: string
  readonly description: string
  readonly phone: string
  readonly customFields: Record<string, string>
}

export interface PeopleQuery {
  readonly page: number
  readonly pageSize: number
  readonly search: string
  readonly assigned: '' | 'true' | 'false'
}

function parse<T>(schema: z.ZodType<T>, data: unknown): T {
  const result = schema.safeParse(data)
  if (!result.success) throw new ApiError(502, 'El servidor respondió en un formato inesperado.')
  return result.data
}

const toPerson = (p: z.infer<typeof personSchema>): Person => ({
  id: p.id,
  resourceId: p.resource_id,
  name: p.name,
  code: p.code,
  description: p.description,
  phone: p.phone,
  customFields: p.custom_fields,
  vehicle: p.vehicle,
})

const toBody = (input: PersonInput) => ({
  name: input.name,
  code: input.code,
  description: input.description,
  phone: input.phone,
  custom_fields: input.customFields,
})

export const peopleApi = {
  async list(kind: PersonKind, query: PeopleQuery) {
    const { data } = await apiClient.get<unknown>(`/${kind}`, {
      params: { page: query.page, page_size: query.pageSize, q: query.search || undefined, assigned: query.assigned || undefined },
    })
    const page = parse(pageSchema, data)
    return { items: page.items.map(toPerson), total: page.total }
  },
  async create(kind: PersonKind, input: PersonInput): Promise<Person> {
    const { data } = await apiClient.post<unknown>(`/${kind}`, toBody(input))
    return toPerson(parse(personSchema, data))
  },
  /** PATCH: el backend lee-fusiona-escribe en Wialon (nunca se pierden campos, RF-27). */
  async update(kind: PersonKind, person: Person, input: PersonInput): Promise<Person> {
    const { data } = await apiClient.patch<unknown>(`/${kind}/${person.resourceId}/${person.id}`, toBody(input))
    return toPerson(parse(personSchema, data))
  },
  async remove(kind: PersonKind, person: Person): Promise<void> {
    await apiClient.delete(`/${kind}/${person.resourceId}/${person.id}`)
  },
  async assign(kind: PersonKind, person: Person, vehicleId: number): Promise<void> {
    await apiClient.put(`/vehicles/${vehicleId}/${kind}/${person.resourceId}/${person.id}`)
  },
  async unassign(kind: PersonKind, person: Person, vehicleId: number): Promise<void> {
    await apiClient.delete(`/vehicles/${vehicleId}/${kind}/${person.resourceId}/${person.id}`)
  },
}

export const peopleKeys = {
  all: (kind: PersonKind) => ['people', kind] as const,
  list: (kind: PersonKind, q: PeopleQuery) => ['people', kind, 'list', q] as const,
}
