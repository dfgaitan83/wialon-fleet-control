/**
 * Integración de rutas + layouts + login con el MISMO mapa de rutas de producción.
 * Se inyecta un AuthService falso (Inversión de dependencias): no hay red ni backend.
 */
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'

import { ApiError } from '@/shared/api/problem'
import { AuthProvider } from '@/shared/auth/AuthProvider'
import { tokenStorage } from '@/shared/auth/tokenStorage'
import type { AuthService, AuthUser, Permission } from '@/shared/auth/types'

import { routes } from './router'

function user(permissions: Permission[]): AuthUser {
  return { id: '1', email: 'ana@flota.co', fullName: 'Ana Gómez', permissions }
}

/** AuthService falso: acepta la contraseña "correcta" y devuelve el usuario indicado. */
function fakeService(sessionUser: AuthUser): AuthService {
  return {
    login: async ({ password }) => {
      if (password !== 'correcta') throw new ApiError(401, 'Email o contraseña incorrectos')
      return { accessToken: 'jwt', user: sessionUser }
    },
    me: async () => sessionUser,
  }
}

function renderAt(path: string, service: AuthService = fakeService(user(['*:*']))) {
  const router = createMemoryRouter(routes, { initialEntries: [path] }) // rutas REALES en memoria
  render(
    <AuthProvider service={service}>
      <RouterProvider router={router} />
    </AuthProvider>,
  )
  return router
}

async function loginAs(password = 'correcta') {
  await userEvent.type(screen.getByLabelText('Correo electrónico'), 'ana@flota.co')
  await userEvent.type(screen.getByLabelText('Contraseña'), password)
  await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }))
}

describe('Router y layouts', () => {
  beforeEach(() => tokenStorage.clear())

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

  it('el administrador (*:*) ve los 7 módulos del menú', async () => {
    tokenStorage.set('jwt')
    renderAt('/app')

    const nav = await screen.findByRole('navigation', { name: 'Principal' })

    expect(within(nav).getAllByRole('link')).toHaveLength(7)
    expect(within(nav).getByRole('link', { name: 'Usuarios' })).toBeInTheDocument()
  })

  it('un visualizador no ve "Usuarios" y si escribe la URL ve "Acceso restringido"', async () => {
    tokenStorage.set('jwt')
    renderAt('/app/users', fakeService(user(['dashboard:read', 'vehicles:read'])))

    const nav = await screen.findByRole('navigation', { name: 'Principal' })

    expect(within(nav).queryByRole('link', { name: 'Usuarios' })).not.toBeInTheDocument()
    expect(screen.getByText('Acceso restringido')).toBeInTheDocument()
  })

  it('"Cerrar sesión" borra la sesión y vuelve a la landing', async () => {
    tokenStorage.set('jwt')
    renderAt('/app')
    await screen.findByText('Ana Gómez')

    await userEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }))

    expect(screen.getByRole('heading', { level: 1, name: /Tu flota/ })).toBeInTheDocument()
    expect(tokenStorage.get()).toBeNull()
  })

  it('con sesión activa, /login redirige al panel', async () => {
    tokenStorage.set('jwt')
    const router = renderAt('/login')

    await screen.findByRole('navigation', { name: 'Principal' })

    expect(router.state.location.pathname).toBe('/app')
  })
})
