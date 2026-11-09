/**
 * Acceso a la API de gestión de usuarios (RF-06), con contratos validados (zod).
 *
 * Contrato (backend/app/api/v1/users.py):
 *   GET    /users?page&page_size&q        -> { items: UserAdmin[], total, page, page_size }
 *   POST   /users {email,full_name,role}  -> { user, temporary_password }   (201)
 *   PATCH  /users/:id {full_name?,role?,is_active?} -> UserAdmin
 *   POST   /users/:id/reset-password      -> { temporary_password }
 *   GET    /roles                         -> [{ name, label, permissions[] }]
 */
import { z } from 'zod'

import { apiClient } from '@/shared/api/client'
import { ApiError } from '@/shared/api/problem'

const userAdminSchema = z.object({
  id: z.number(),
  email: z.email(),
  full_name: z.string(),
  role: z.string(),
  role_label: z.string(),
  permissions: z.array(z.string()),
  must_change_password: z.boolean(),
  is_active: z.boolean(),
  is_locked: z.boolean(),
})

const pageSchema = z.object({
  items: z.array(userAdminSchema),
  total: z.number().int(),
  page: z.number().int(),
  page_size: z.number().int(),
})

const roleSchema = z.object({ name: z.string(), label: z.string(), permissions: z.array(z.string()) })
const temporarySchema = z.object({ temporary_password: z.string().min(1) })
const createdSchema = temporarySchema.extend({ user: userAdminSchema })

export interface ManagedUser {
  readonly id: number
  readonly email: string
  readonly fullName: string
  readonly role: string
  readonly roleLabel: string
  readonly isActive: boolean
  readonly isLocked: boolean
  readonly mustChangePassword: boolean
}

export interface UsersPage {
  readonly items: readonly ManagedUser[]
  readonly total: number
  readonly page: number
  readonly pageSize: number
}

export interface Role {
  readonly name: string
  readonly label: string
}

export interface NewUserInput {
  readonly email: string
  readonly fullName: string
  readonly role: string
}

export interface UserChanges {
  readonly role?: string
  readonly isActive?: boolean
}

function parse<T>(schema: z.ZodType<T>, data: unknown): T {
  const result = schema.safeParse(data)
  if (!result.success) throw new ApiError(502, 'El servidor respondió en un formato inesperado.')
  return result.data
}

function toManagedUser(dto: z.infer<typeof userAdminSchema>): ManagedUser {
  return {
    id: dto.id,
    email: dto.email,
    fullName: dto.full_name,
    role: dto.role,
    roleLabel: dto.role_label,
    isActive: dto.is_active,
    isLocked: dto.is_locked,
    mustChangePassword: dto.must_change_password,
  }
}

export const usersApi = {
  async list(params: { page: number; pageSize: number; search: string }): Promise<UsersPage> {
    const { data } = await apiClient.get<unknown>('/users', {
      params: { page: params.page, page_size: params.pageSize, q: params.search || undefined },
    })
    const page = parse(pageSchema, data)
    return { items: page.items.map(toManagedUser), total: page.total, page: page.page, pageSize: page.page_size }
  },

  async roles(): Promise<Role[]> {
    const { data } = await apiClient.get<unknown>('/roles')
    return parse(z.array(roleSchema), data).map(({ name, label }) => ({ name, label }))
  },

  async create(input: NewUserInput): Promise<{ user: ManagedUser; temporaryPassword: string }> {
    const { data } = await apiClient.post<unknown>('/users', {
      email: input.email,
      full_name: input.fullName,
      role: input.role,
    })
    const created = parse(createdSchema, data)
    return { user: toManagedUser(created.user), temporaryPassword: created.temporary_password }
  },

  async update(id: number, changes: UserChanges): Promise<ManagedUser> {
    const { data } = await apiClient.patch<unknown>(`/users/${id}`, {
      role: changes.role,
      is_active: changes.isActive,
    })
    return toManagedUser(parse(userAdminSchema, data))
  },

  async resetPassword(id: number): Promise<string> {
    const { data } = await apiClient.post<unknown>(`/users/${id}/reset-password`)
    return parse(temporarySchema, data).temporary_password
  },
}

/** Claves de caché de TanStack Query: un solo lugar (invalidar = mismo prefijo). */
export const usersKeys = {
  all: ['users'] as const,
  list: (page: number, search: string) => ['users', 'list', page, search] as const,
  roles: ['roles'] as const,
}
