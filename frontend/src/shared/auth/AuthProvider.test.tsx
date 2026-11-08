/**
 * Flujo de sesión completo: login, restauración tras F5, token inválido, 401 y guardias.
 * La red se simula con mockApi: se prueban el AuthProvider, el cliente axios y
 * sus interceptores REALES trabajando juntos.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from '@/shared/api/client'
import { type MockHandler, mockApi } from '@/test/mockAdapter'

import { AuthProvider } from './AuthProvider'
import { RequireAuth } from './RequireAuth'
import { RequirePermission } from './RequirePermission'
import { tokenStorage } from './tokenStorage'
import { useAuth } from './useAuth'

const ADMIN = { id: '1', email: 'admin@demo.co', full_name: 'Admin Demo', permissions: ['*:*'] }
const OPERATOR = { id: '2', email: 'op@demo.co', full_name: 'Operador', permissions: ['vehicles:read'] }

/** Componente de prueba que muestra el estado de la sesión y permite login/logout. */
function SessionProbe() {
  const { status, user, login, logout } = useAuth()
  return (
    <div>
      <p>estado: {status}</p>
      <p>usuario: {user?.fullName ?? 'ninguno'}</p>
      <button onClick={() => void login({ email: 'admin@demo.co', password: 'x' })}>entrar</button>
      <button onClick={logout}>salir</button>
    </div>
  )
}

/** Monta la app con rutas: pública /login y protegida /privada. */
function renderApp(initialPath = '/privada') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <AuthProvider>
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

  beforeEach(() => tokenStorage.clear())
  afterEach(() => restore())

  it('sin sesión, una ruta protegida redirige a /login', () => {
    renderApp()

    expect(screen.getByText('pantalla de login')).toBeInTheDocument()
    expect(screen.getByText('estado: anonymous')).toBeInTheDocument()
  })

  it('login correcto guarda el token y abre la sesión', async () => {
    useApi(() => ({ status: 200, data: { access_token: 'jwt-admin', token_type: 'bearer', user: ADMIN } }))
    renderApp('/login')

    await userEvent.click(screen.getByRole('button', { name: 'entrar' }))

    expect(await screen.findByText('estado: authenticated')).toBeInTheDocument()
    expect(screen.getByText('usuario: Admin Demo')).toBeInTheDocument()
    expect(tokenStorage.get()).toBe('jwt-admin')
  })

  it('tras un F5 con token válido, restaura la sesión con /auth/me', async () => {
    tokenStorage.set('jwt-guardado')
    useApi((config) =>
      config.url === '/auth/me' ? { status: 200, data: ADMIN } : { status: 404, data: null },
    )

    renderApp()

    expect(screen.getByText('Verificando sesión…')).toBeInTheDocument() // sin "parpadeo" a /login
    expect(await screen.findByText('zona privada')).toBeInTheDocument()
  })

  it('tras un F5 con token expirado, borra el token y manda a /login', async () => {
    tokenStorage.set('jwt-expirado')
    useApi(() => ({ status: 401, data: { title: 'Token expirado', status: 401 } }))

    renderApp()

    expect(await screen.findByText('pantalla de login')).toBeInTheDocument()
    expect(tokenStorage.get()).toBeNull()
  })

  it('un 401 en CUALQUIER petición posterior cierra la sesión automáticamente', async () => {
    tokenStorage.set('jwt-valido')
    let expired = false
    useApi((config) => {
      if (config.url === '/auth/me') return { status: 200, data: ADMIN }
      expired = true
      return { status: 401, data: { title: 'Token expirado', status: 401 } }
    })
    renderApp()
    await screen.findByText('zona privada')

    await apiClient.get('/vehicles').catch(() => undefined) // el backend responde 401

    expect(expired).toBe(true)
    expect(await screen.findByText('pantalla de login')).toBeInTheDocument()
  })

  it('logout borra el token y vuelve a /login', async () => {
    tokenStorage.set('jwt-valido')
    useApi(() => ({ status: 200, data: ADMIN }))
    renderApp()
    await screen.findByText('zona privada')

    await userEvent.click(screen.getByRole('button', { name: 'salir' }))

    expect(screen.getByText('pantalla de login')).toBeInTheDocument()
    expect(tokenStorage.get()).toBeNull()
  })

  it('RequirePermission oculta la sección si falta el permiso', async () => {
    tokenStorage.set('jwt-operador')
    useApi(() => ({ status: 200, data: OPERATOR }))

    renderApp('/usuarios')

    expect(await screen.findByText('Acceso restringido')).toBeInTheDocument()
    expect(screen.queryByText('gestión de usuarios')).not.toBeInTheDocument()
  })

  it('RequirePermission muestra la sección al administrador (*:*)', async () => {
    tokenStorage.set('jwt-admin')
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
