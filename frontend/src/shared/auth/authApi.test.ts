import { afterEach, describe, expect, it } from 'vitest'

import { ApiError } from '@/shared/api/problem'
import { mockApi } from '@/test/mockAdapter'
import { userDto } from '@/test/users'

import { authApi } from './authApi'

describe('authApi (contrato con el backend)', () => {
  let restore: () => void = () => {}
  afterEach(() => restore())

  it('login envía las credenciales y transforma snake_case -> camelCase', async () => {
    let sentBody: unknown
    restore = mockApi((config) => {
      sentBody = JSON.parse(String(config.data))
      return { status: 200, data: { user: userDto({ permissions: ['vehicles:read'] }) } }
    })

    const user = await authApi.login({ email: 'admin@demo.co', password: 'x' })

    expect(sentBody).toEqual({ email: 'admin@demo.co', password: 'x' })
    expect(user).toEqual({
      id: '1',
      email: 'admin@demo.co',
      fullName: 'Admin Demo',
      role: 'admin',
      roleLabel: 'Administrador',
      permissions: ['vehicles:read'],
      mustChangePassword: false,
    })
  })

  it('rechaza una respuesta que no cumple el contrato (no sigue con datos rotos)', async () => {
    restore = mockApi(() => ({ status: 200, data: { user: { email: 'a@b.co' } } }))

    await expect(authApi.login({ email: 'a@b.co', password: 'x' })).rejects.toMatchObject({
      status: 502,
      message: 'El servidor respondió en un formato inesperado.',
    })
  })

  it('me() devuelve el usuario de la sesión', async () => {
    restore = mockApi(() => ({ status: 200, data: userDto() }))

    await expect(authApi.me()).resolves.toMatchObject({ fullName: 'Admin Demo', roleLabel: 'Administrador' })
  })

  it('logout hace POST /auth/logout', async () => {
    let request: { method?: string; url?: string } = {}
    restore = mockApi((config) => {
      request = { method: config.method, url: config.url }
      return { status: 204 }
    })

    await authApi.logout()

    expect(request).toEqual({ method: 'post', url: '/auth/logout' })
  })

  it('credenciales incorrectas llegan como ApiError 401 con el mensaje del servidor', async () => {
    restore = mockApi(() => ({
      status: 401,
      data: { title: 'No autenticado', status: 401, detail: 'Correo o contraseña incorrectos.' },
    }))

    const error = await authApi.login({ email: 'a@b.co', password: 'mala' }).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).message).toBe('Correo o contraseña incorrectos.')
  })
})
