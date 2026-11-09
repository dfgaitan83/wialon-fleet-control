/**
 * Pantalla de Usuarios (RF-06) con el cliente HTTP real y la red simulada (mockApi).
 */
import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'

import { createQueryClient } from '@/app/queryClient'
import { AuthContext } from '@/shared/auth/AuthContext'
import { userHasPermission } from '@/shared/auth/permissions'
import type { AuthContextValue, AuthUser, Permission } from '@/shared/auth/types'
import { mockApi } from '@/test/mockAdapter'
import { authUser } from '@/test/users'

import { UsersPage } from './UsersPage'

const ROLES = [
  { name: 'admin', label: 'Administrador', permissions: [] },
  { name: 'operator', label: 'Operador', permissions: [] },
  { name: 'viewer', label: 'Visualizador', permissions: [] },
]

function userDto(id: number, email: string, overrides: Record<string, unknown> = {}) {
  return {
    id,
    email,
    full_name: `Usuario ${id}`,
    role: 'viewer',
    role_label: 'Visualizador',
    permissions: [],
    must_change_password: false,
    is_active: true,
    is_locked: false,
    ...overrides,
  }
}

function renderPage(me: AuthUser) {
  const auth: AuthContextValue = {
    status: 'authenticated',
    user: me,
    login: async () => {},
    logout: async () => {},
    changePassword: async () => {},
    hasPermission: (p: Permission) => userHasPermission(me, p),
  }
  render(
    <QueryClientProvider client={createQueryClient()}>
      <AuthContext value={auth}>
        <UsersPage />
      </AuthContext>
    </QueryClientProvider>,
  )
}

describe('UsersPage', () => {
  let restore: () => void = () => {}
  afterEach(() => restore())

  it('lista los usuarios con su estado (bloqueado, debe cambiar contraseña, inactivo)', async () => {
    restore = mockApi((config) => {
      if (config.url === '/roles') return { status: 200, data: ROLES }
      return {
        status: 200,
        data: {
          items: [
            userDto(2, 'ana@flota.co', { is_locked: true }),
            userDto(3, 'luis@flota.co', { must_change_password: true }),
            userDto(4, 'baja@flota.co', { is_active: false }),
          ],
          total: 3,
          page: 1,
          page_size: 10,
        },
      }
    })

    renderPage(authUser())

    expect(await screen.findByText('ana@flota.co')).toBeInTheDocument()
    expect(screen.getByText('Bloqueado')).toBeInTheDocument()
    expect(screen.getByText('Debe cambiar contraseña')).toBeInTheDocument()
    expect(screen.getByText('Inactivo')).toBeInTheDocument()
    expect(screen.getByText(/Página 1 de 1 · 3 usuarios/)).toBeInTheDocument()
  })

  it('crear un usuario muestra UNA vez la contraseña temporal generada por el backend', async () => {
    let sent: unknown
    restore = mockApi((config) => {
      if (config.url === '/roles') return { status: 200, data: ROLES }
      if (config.method === 'post') {
        sent = JSON.parse(String(config.data))
        return { status: 201, data: { user: userDto(9, 'nuevo@flota.co'), temporary_password: 'Tmp-9xYz-2026' } }
      }
      return { status: 200, data: { items: [], total: 0, page: 1, page_size: 10 } }
    })
    renderPage(authUser())
    await screen.findByText('Aún no hay usuarios')

    await userEvent.type(screen.getByLabelText('Correo electrónico'), 'nuevo@flota.co')
    await userEvent.type(screen.getByLabelText('Nombre completo'), 'Nuevo Operador')
    await userEvent.selectOptions(screen.getByLabelText('Rol'), 'operator')
    await userEvent.click(screen.getByRole('button', { name: 'Crear usuario' }))

    expect(await screen.findByText('Tmp-9xYz-2026')).toBeInTheDocument()
    expect(sent).toEqual({ email: 'nuevo@flota.co', full_name: 'Nuevo Operador', role: 'operator' })
  })

  it('las acciones destructivas piden confirmación antes de llamar al servidor', async () => {
    const calls: string[] = []
    restore = mockApi((config) => {
      calls.push(`${config.method} ${config.url}`)
      if (config.url === '/roles') return { status: 200, data: ROLES }
      return { status: 200, data: { items: [userDto(2, 'ana@flota.co')], total: 1, page: 1, page_size: 10 } }
    })
    renderPage(authUser())
    const row = (await screen.findByText('ana@flota.co')).closest('tr') as HTMLElement

    await userEvent.click(within(row).getByRole('button', { name: 'Desactivar' }))

    expect(within(row).getByRole('group', { name: 'Confirmar acción' })).toBeInTheDocument()
    expect(calls.some((c) => c.startsWith('patch'))).toBe(false) // todavía nada enviado
  })

  it('sin "users:write" (solo lectura) no aparece el formulario ni las acciones', async () => {
    restore = mockApi((config) =>
      config.url === '/roles'
        ? { status: 200, data: ROLES }
        : { status: 200, data: { items: [userDto(2, 'ana@flota.co')], total: 1, page: 1, page_size: 10 } },
    )

    renderPage(authUser(['users:read']))

    expect(await screen.findByText('ana@flota.co')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Crear usuario' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Desactivar' })).not.toBeInTheDocument()
  })
})
