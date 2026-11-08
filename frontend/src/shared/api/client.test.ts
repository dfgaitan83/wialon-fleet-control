import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { tokenStorage } from '@/shared/auth/tokenStorage'
import { mockApi } from '@/test/mockAdapter'

import { apiClient, setUnauthorizedHandler } from './client'
import { ApiError } from './problem'

describe('apiClient', () => {
  let restore: () => void = () => {}

  beforeEach(() => tokenStorage.clear())
  afterEach(() => {
    restore() // devuelve el adaptador real de axios
    setUnauthorizedHandler(null)
  })

  it('añade "Authorization: Bearer <token>" cuando hay sesión', async () => {
    // Arrange
    tokenStorage.set('jwt-123')
    let authHeader: unknown
    restore = mockApi((config) => {
      authHeader = config.headers.get('Authorization')
      return { status: 200, data: {} }
    })

    // Act
    await apiClient.get('/vehicles')

    // Assert
    expect(authHeader).toBe('Bearer jwt-123')
  })

  it('NO envía cabecera Authorization sin sesión', async () => {
    let authHeader: unknown = 'sin-leer'
    restore = mockApi((config) => {
      authHeader = config.headers.get('Authorization')
      return { status: 200, data: {} }
    })

    await apiClient.get('/health')

    expect(authHeader).toBeUndefined()
  })

  it('convierte cualquier error HTTP en ApiError', async () => {
    restore = mockApi(() => ({ status: 403, data: { title: 'Prohibido', status: 403 } }))

    await expect(apiClient.get('/users')).rejects.toBeInstanceOf(ApiError)
  })

  it('ante un 401 avisa a la capa de auth para cerrar la sesión', async () => {
    const onUnauthorized = vi.fn()
    setUnauthorizedHandler(onUnauthorized)
    restore = mockApi(() => ({ status: 401, data: { title: 'Token expirado', status: 401 } }))

    await expect(apiClient.get('/vehicles')).rejects.toMatchObject({ status: 401 })

    expect(onUnauthorized).toHaveBeenCalledOnce()
  })

  it('un 401 en /auth/login (credenciales malas) NO dispara el cierre de sesión', async () => {
    const onUnauthorized = vi.fn()
    setUnauthorizedHandler(onUnauthorized)
    restore = mockApi(() => ({ status: 401, data: { title: 'Credenciales inválidas', status: 401 } }))

    await expect(apiClient.post('/auth/login', {})).rejects.toMatchObject({ status: 401 })

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
