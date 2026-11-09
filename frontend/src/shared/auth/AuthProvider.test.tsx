/**
 * Flujo de sesión completo: login, restauración tras F5, sesión expirada, refresh y guardias.
 * La red se simula con mockApi: se prueban el AuthProvider, el cliente axios y
 * sus interceptores REALES trabajando juntos.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from '@/shared/api/client'
import { clearCsrfCookie, setCsrfCookie } from '@/test/cookies'
import { type MockHandler, mockApi } from '@/test/mockAdapter'
import { userDto } from '@/test/users'

import { authApi } from './authApi'
import { AuthProvider } from './AuthProvider'
import { RequireAuth } from './RequireAuth'
import { RequirePermission } from './RequirePermission'
import { useAuth } from './useAuth'

const ADMIN = userDto()
const OPERATOR = userDto({ id: 2, full_name: 'Operador', role: 'operator', permissions: ['vehicles:read'] })

/** Componente de prueba que muestra el estado de la sesión y permite login/logout. */
function SessionProbe() {
  const { status, user, login, logout } = useAuth()
  return (
    <div>
      <p>estado: {status}</p>
      <p>usuario: {user?.fullName ?? 'ninguno'}</p>
      <button onClick={() => void login({ email: 'admin@demo.co', password: 'x' })}>entrar</button>
      <button onClick={() => void logout()}>salir</button>
    </div>
  )
}

/** Monta la app con rutas: pública /login y protegida /privada. */
function renderApp(initialPath = '/privada') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      {/* Se inyecta el servicio HTTP REAL: la red la simula mockApi. */}
      <AuthProvider service={authApi}>
        <Routes>
          <Route path="/login" element={<p>pantalla de login</p>} />
          <Route element={<RequireAuth />}>
            <Route path="/privada" element={<p>zona privada</p>} />
            <Route
              path="/usuarios"
              element={
                <RequirePermission permission="users:write">
                  <p>gestión de usuarios</p>
                </RequirePermission>
              }
            />
          </Route>
        </Routes>
        <SessionProbe />
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('AuthProvider + guardias', () => {
  let restore: () => void = () => {}
  const useApi = (handler: MockHandler) => {
    restore = mockApi(handler)
  }

  beforeEach(() => clearCsrfCookie())
  afterEach(() => restore())

  it('sin indicio de sesión: anónimo al instante y SIN peticiones al backend', () => {
    const handler = vi.fn(() => ({ status: 500 }))
    useApi(handler)

    renderApp()

    expect(screen.getByText('pantalla de login')).toBeInTheDocument()
    expect(screen.getByText('estado: anonymous')).toBeInTheDocument()
    expect(handler).not.toHaveBeenCalled()
  })

  it('login correcto abre la sesión con el usuario que devuelve el backend', async () => {
    useApi(() => ({ status: 200, data: { user: ADMIN } }))
    renderApp('/login')

    await userEvent.click(screen.getByRole('button', { name: 'entrar' }))

    expect(await screen.findByText('estado: authenticated')).toBeInTheDocument()
    expect(screen.getByText('usuario: Admin Demo')).toBeInTheDocument()
  })

  it('tras un F5 con sesión, la restaura con /auth/me sin "parpadeo" a /login', async () => {
    setCsrfCookie()
    useApi((config) => (config.url === '/auth/me' ? { status: 200, data: ADMIN } : { status: 404 }))

    renderApp()

    expect(screen.getByText('Verificando sesión…')).toBeInTheDocument()
    expect(await screen.findByText('zona privada')).toBeInTheDocument()
  })

  it('tras un F5 con el access expirado, renueva la sesión sola y entra', async () => {
    setCsrfCookie()
    let refreshed = false
    useApi((config) => {
      if (config.url === '/auth/refresh') {
        refreshed = true
        return { status: 200, data: { user: ADMIN } }
      }
      return refreshed ? { status: 200, data: ADMIN } : { status: 401, data: { title: 'x', status: 401 } }
    })

    renderApp()

    expect(await screen.findByText('zona privada')).toBeInTheDocument()
  })

  it('tras un F5 con la sesión vencida del todo, manda a /login', async () => {
    setCsrfCookie()
    useApi(() => ({ status: 401, data: { title: 'Sesión expirada', status: 401 } }))

    renderApp()

    expect(await screen.findByText('pantalla de login')).toBeInTheDocument()
  })

  it('si una petición posterior no logra renovar la sesión, se cierra automáticamente', async () => {
    setCsrfCookie()
    useApi((config) =>
      config.url === '/auth/me' ? { status: 200, data: ADMIN } : { status: 401, data: { title: 'x', status: 401 } },
    )
    renderApp()
    await screen.findByText('zona privada')

    await apiClient.get('/vehicles').catch(() => undefined) // 401 y el refresh también 401

    expect(await screen.findByText('pantalla de login')).toBeInTheDocument()
  })

  it('logout avisa al SERVIDOR (POST /auth/logout con CSRF) y vuelve a /login', async () => {
    setCsrfCookie('csrf-xyz')
    let logoutHeader: unknown
    useApi((config) => {
      if (config.url === '/auth/logout') {
        logoutHeader = config.headers.get('X-CSRF-Token')
        return { status: 204 }
      }
      return { status: 200, data: ADMIN }
    })
    renderApp()
    await screen.findByText('zona privada')

    await userEvent.click(screen.getByRole('button', { name: 'salir' }))

    expect(await screen.findByText('pantalla de login')).toBeInTheDocument()
    expect(logoutHeader).toBe('csrf-xyz')
  })

  it('aunque el logout falle por red, la UI sale de la sesión', async () => {
    setCsrfCookie()
    useApi((config) => (config.url === '/auth/logout' ? 'network-error' : { status: 200, data: ADMIN }))
    renderApp()
    await screen.findByText('zona privada')

    await userEvent.click(screen.getByRole('button', { name: 'salir' }))

    expect(await screen.findByText('pantalla de login')).toBeInTheDocument()
  })

  it('RequirePermission oculta la sección si falta el permiso', async () => {
    setCsrfCookie()
    useApi(() => ({ status: 200, data: OPERATOR }))

    renderApp('/usuarios')

    expect(await screen.findByText('Acceso restringido')).toBeInTheDocument()
    expect(screen.queryByText('gestión de usuarios')).not.toBeInTheDocument()
  })

  it('RequirePermission muestra la sección al administrador (permiso explícito)', async () => {
    setCsrfCookie()
    useApi(() => ({ status: 200, data: ADMIN }))

    renderApp('/usuarios')

    expect(await screen.findByText('gestión de usuarios')).toBeInTheDocument()
  })

  it('useAuth fuera de <AuthProvider> falla con un mensaje claro', () => {
    function Orphan() {
      useAuth()
      return null
    }
    // React registra el error en consola; se silencia para no ensuciar la salida del test.
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})

    expect(() => render(<Orphan />)).toThrow('useAuth debe usarse dentro de <AuthProvider>')
    spy.mockRestore()
  })
})
