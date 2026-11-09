import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearCsrfCookie, setCsrfCookie } from '@/test/cookies'
import { mockApi } from '@/test/mockAdapter'

import { apiClient, setUnauthorizedHandler } from './client'
import { ApiError } from './problem'

describe('apiClient', () => {
  let restore: () => void = () => {}

  beforeEach(() => clearCsrfCookie())
  afterEach(() => {
    restore() // devuelve el adaptador real de axios
    setUnauthorizedHandler(null)
  })

  it('usa la URL relativa /api/v1 (mismo origen: proxy de Vite / rewrite de Vercel)', () => {
    expect(apiClient.defaults.baseURL).toBe('/api/v1')
    expect(apiClient.defaults.withCredentials).toBe(true) // envía las cookies de sesión
  })

  it('añade X-CSRF-Token (copiado de la cookie) en las peticiones que modifican datos', async () => {
    setCsrfCookie('token-csrf-123')
    let header: unknown
    restore = mockApi((config) => {
      header = config.headers.get('X-CSRF-Token')
      return { status: 204 }
    })

    await apiClient.post('/drivers', {})

    expect(header).toBe('token-csrf-123')
  })

  it('NO añade X-CSRF-Token en lecturas (GET)', async () => {
    setCsrfCookie('token-csrf-123')
    let header: unknown = 'sin-leer'
    restore = mockApi((config) => {
      header = config.headers.get('X-CSRF-Token')
      return { status: 200, data: {} }
    })

    await apiClient.get('/vehicles')

    expect(header).toBeUndefined()
  })

  it('nunca envía cabecera Authorization: la sesión viaja en cookies HttpOnly', async () => {
    let auth: unknown = 'sin-leer'
    restore = mockApi((config) => {
      auth = config.headers.get('Authorization')
      return { status: 200, data: {} }
    })

    await apiClient.get('/vehicles')

    expect(auth).toBeUndefined()
  })

  it('convierte cualquier error HTTP en ApiError', async () => {
    restore = mockApi(() => ({ status: 403, data: { title: 'Prohibido', status: 403 } }))

    await expect(apiClient.get('/users')).rejects.toBeInstanceOf(ApiError)
  })

  it('ante un 401 renueva la sesión y repite la petición sin que el usuario lo note', async () => {
    const calls: string[] = []
    let refreshed = false
    restore = mockApi((config) => {
      calls.push(config.url ?? '')
      if (config.url === '/auth/refresh') {
        refreshed = true
        return { status: 200, data: {} }
      }
      return refreshed ? { status: 200, data: { ok: true } } : { status: 401, data: { title: 'x', status: 401 } }
    })

    const { data } = await apiClient.get('/vehicles')

    expect(data).toEqual({ ok: true })
    expect(calls).toEqual(['/vehicles', '/auth/refresh', '/vehicles'])
  })

  it('varios 401 simultáneos comparten UN solo refresh (single-flight)', async () => {
    let refreshes = 0
    let refreshed = false
    restore = mockApi((config) => {
      if (config.url === '/auth/refresh') {
        refreshes += 1
        refreshed = true
        return { status: 200, data: {} }
      }
      return refreshed ? { status: 200, data: {} } : { status: 401, data: { title: 'x', status: 401 } }
    })

    await Promise.all([apiClient.get('/a'), apiClient.get('/b'), apiClient.get('/c')])

    expect(refreshes).toBe(1)
  })

  it('si el refresh falla, avisa a la capa de auth y rechaza con 401', async () => {
    const onUnauthorized = vi.fn()
    setUnauthorizedHandler(onUnauthorized)
    restore = mockApi(() => ({ status: 401, data: { title: 'Sesión expirada', status: 401 } }))

    await expect(apiClient.get('/vehicles')).rejects.toMatchObject({ status: 401 })

    expect(onUnauthorized).toHaveBeenCalledOnce()
  })

  it('no reintenta en bucle: si tras renovar sigue en 401, se rinde', async () => {
    let vehicleCalls = 0
    restore = mockApi((config) => {
      if (config.url === '/auth/refresh') return { status: 200, data: {} }
      vehicleCalls += 1
      return { status: 401, data: { title: 'x', status: 401 } }
    })

    await expect(apiClient.get('/vehicles')).rejects.toMatchObject({ status: 401 })

    expect(vehicleCalls).toBe(2) // original + UN reintento
  })

  it('un 401 en /auth/login (credenciales malas) NO intenta renovar ni cierra la sesión', async () => {
    const onUnauthorized = vi.fn()
    setUnauthorizedHandler(onUnauthorized)
    const calls: string[] = []
    restore = mockApi((config) => {
      calls.push(config.url ?? '')
      return { status: 401, data: { title: 'Credenciales inválidas', status: 401 } }
    })

    await expect(apiClient.post('/auth/login', {})).rejects.toMatchObject({ status: 401 })

    expect(calls).toEqual(['/auth/login'])
    expect(onUnauthorized).not.toHaveBeenCalled()
  })

  it('la función de limpieza des-registra el handler', async () => {
    const onUnauthorized = vi.fn()
    const unregister = setUnauthorizedHandler(onUnauthorized)
    unregister()
    restore = mockApi(() => ({ status: 401, data: { title: 'x', status: 401 } }))

    await expect(apiClient.get('/vehicles')).rejects.toBeInstanceOf(ApiError)

    expect(onUnauthorized).not.toHaveBeenCalled()
  })
})
