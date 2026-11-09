/**
 * Integración de rutas + layouts + login con el MISMO mapa de rutas de producción.
 * Se inyecta un AuthService falso (Inversión de dependencias): no hay red ni backend.
 */
import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'

import { ApiError } from '@/shared/api/problem'
import { AuthProvider } from '@/shared/auth/AuthProvider'
import type { AuthService, AuthUser, Permission } from '@/shared/auth/types'
import { clearCsrfCookie, setCsrfCookie } from '@/test/cookies'
import { authUser } from '@/test/users'

import { createQueryClient } from './queryClient'
import { routes } from './router'

function user(permissions?: Permission[]): AuthUser {
  return authUser(permissions)
}

/** AuthService falso: acepta la contraseña "correcta" y devuelve el usuario indicado. */
function fakeService(sessionUser: AuthUser): AuthService {
  return {
    login: async ({ password }) => {
      if (password !== 'correcta') throw new ApiError(401, 'Email o contraseña incorrectos')
      return sessionUser
    },
    me: async () => sessionUser,
    logout: async () => undefined,
    changePassword: async () => ({ ...sessionUser, mustChangePassword: false }),
  }
}

function renderAt(path: string, service: AuthService = fakeService(user())) {
  const router = createMemoryRouter(routes, { initialEntries: [path] }) // rutas REALES en memoria
  render(
    <QueryClientProvider client={createQueryClient()}>
      <AuthProvider service={service}>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>,
  )
  return router
}

async function loginAs(password = 'correcta') {
  await userEvent.type(screen.getByLabelText('Correo electrónico'), 'ana@flota.co')
  await userEvent.type(screen.getByLabelText('Contraseña'), password)
  await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }))
}

describe('Router y layouts', () => {
  beforeEach(() => clearCsrfCookie())

  it('"/" muestra la landing dentro del PublicLayout con acceso a "Ingresar"', () => {
    renderAt('/')

    expect(screen.getByRole('heading', { level: 1, name: /Tu flota/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ingresar' })).toHaveAttribute('href', '/login')
    expect(screen.getByRole('contentinfo')).toHaveTextContent('Fleet Control') // <footer>
  })

  it('una URL inexistente muestra la página 404', () => {
    renderAt('/no-existe')

    expect(screen.getByText('Página no encontrada')).toBeInTheDocument()
  })

  it('una ruta privada sin sesión redirige al login', () => {
    renderAt('/app/vehicles')

    expect(screen.getByRole('heading', { name: 'Inicia sesión' })).toBeInTheDocument()
  })

  it('el login valida en el cliente antes de llamar al servidor', async () => {
    renderAt('/login')

    await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }))

    expect(screen.getByText('Ingresa tu correo')).toBeInTheDocument()
    expect(screen.getByText('Ingresa tu contraseña')).toBeInTheDocument()
  })

  it('muestra el mensaje del servidor si las credenciales son incorrectas', async () => {
    renderAt('/login')

    await loginAs('mala')

    expect(await screen.findByRole('alert')).toHaveTextContent('Email o contraseña incorrectos')
  })

  it('tras el login vuelve a la página que se intentaba abrir, dentro del AppLayout', async () => {
    const router = renderAt('/app/vehicles')

    await loginAs()

    expect(await screen.findByRole('heading', { name: 'Vehículos' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/app/vehicles')
    const nav = screen.getByRole('navigation', { name: 'Principal' })
    expect(within(nav).getByRole('link', { name: 'Vehículos' })).toHaveAttribute('aria-current', 'page')
  })

  it('el administrador ve los 7 módulos del menú', async () => {
    setCsrfCookie()
    renderAt('/app')

    const nav = await screen.findByRole('navigation', { name: 'Principal' })

    expect(within(nav).getAllByRole('link')).toHaveLength(7)
    expect(within(nav).getByRole('link', { name: 'Usuarios' })).toBeInTheDocument()
  })

  it('un visualizador no ve "Usuarios" y si escribe la URL ve "Acceso restringido"', async () => {
    setCsrfCookie()
    renderAt('/app/users', fakeService(user(['dashboard:read', 'vehicles:read'])))

    const nav = await screen.findByRole('navigation', { name: 'Principal' })

    expect(within(nav).queryByRole('link', { name: 'Usuarios' })).not.toBeInTheDocument()
    expect(screen.getByText('Acceso restringido')).toBeInTheDocument()
  })

  it('"Cerrar sesión" borra la sesión y vuelve a la landing', async () => {
    setCsrfCookie()
    renderAt('/app')
    await screen.findByText('Ana Gómez')

    await userEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }))

    expect(screen.getByRole('heading', { level: 1, name: /Tu flota/ })).toBeInTheDocument()
  })

  it('RF-06: con contraseña temporal solo puede ir a "Crea tu contraseña" y después entra al panel', async () => {
    setCsrfCookie()
    const temporary: AuthUser = { ...user(), mustChangePassword: true }
    const router = renderAt('/app/vehicles', fakeService(temporary))

    expect(await screen.findByRole('heading', { name: 'Crea tu contraseña' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/cambiar-contrasena')

    await userEvent.type(screen.getByLabelText('Contraseña temporal'), 'Temporal-123456')
    await userEvent.type(screen.getByLabelText('Nueva contraseña'), 'Nueva-Clave-2026')
    await userEvent.type(screen.getByLabelText('Repite la nueva contraseña'), 'Nueva-Clave-2026')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar contraseña' }))

    expect(await screen.findByRole('navigation', { name: 'Principal' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/app')
  })

  it('RF-06: el cambio de contraseña valida la política antes de enviar', async () => {
    setCsrfCookie()
    renderAt('/cambiar-contrasena', fakeService({ ...user(), mustChangePassword: true }))
    await screen.findByRole('heading', { name: 'Crea tu contraseña' })

    await userEvent.type(screen.getByLabelText('Contraseña temporal'), 'Temporal-123456')
    await userEvent.type(screen.getByLabelText('Nueva contraseña'), 'corta1')
    await userEvent.type(screen.getByLabelText('Repite la nueva contraseña'), 'otra-distinta')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar contraseña' }))

    expect(screen.getByText('Debe tener al menos 12 caracteres')).toBeInTheDocument()
    expect(screen.getByText('Las contraseñas no coinciden')).toBeInTheDocument()
  })

  it('móvil: el botón "Menú" muestra la sección actual, se abre y se cierra al elegir', async () => {
    setCsrfCookie()
    const router = renderAt('/app/vehicles')
    const toggle = await screen.findByRole('button', { name: /^Menú/ })
    expect(toggle).toHaveTextContent('Menú · Vehículos') // dice en qué sección estás
    expect(toggle).toHaveAttribute('aria-expanded', 'false')

    await userEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')

    const nav = screen.getByRole('navigation', { name: 'Principal' })
    await userEvent.click(within(nav).getByRole('link', { name: 'Usuarios' }))
    expect(router.state.location.pathname).toBe('/app/users')
    expect(toggle).toHaveTextContent('Menú · Usuarios')
    expect(toggle).toHaveAttribute('aria-expanded', 'false') // se cerró al elegir
  })

  it('con sesión activa, /login redirige al panel', async () => {
    setCsrfCookie()
    const router = renderAt('/login')

    await screen.findByRole('navigation', { name: 'Principal' })

    expect(router.state.location.pathname).toBe('/app')
  })
})
