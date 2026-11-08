import { afterEach, describe, expect, it } from 'vitest'

import { ApiError } from '@/shared/api/problem'
import { mockApi } from '@/test/mockAdapter'

import { authApi } from './authApi'

const USER_DTO = { id: 1, email: 'admin@demo.co', full_name: 'Admin Demo', permissions: ['*:*'] }

describe('authApi (contrato con el backend)', () => {
  let restore: () => void = () => {}
  afterEach(() => restore())

  it('login envía las credenciales y transforma snake_case -> camelCase', async () => {
    let sentBody: unknown
    restore = mockApi((config) => {
      sentBody = JSON.parse(String(config.data))
      return { status: 200, data: { access_token: 'jwt', token_type: 'Bearer', user: USER_DTO } }
    })

    const result = await authApi.login({ email: 'admin@demo.co', password: 'x' })

    expect(sentBody).toEqual({ email: 'admin@demo.co', password: 'x' })
    expect(result).toEqual({
      accessToken: 'jwt',
      user: { id: '1', email: 'admin@demo.co', fullName: 'Admin Demo', permissions: ['*:*'] },
    })
  })

  it('rechaza una respuesta que no cumple el contrato (no sigue con datos rotos)', async () => {
    restore = mockApi(() => ({ status: 200, data: { token: 'falta-access_token' } }))

    await expect(authApi.login({ email: 'a@b.co', password: 'x' })).rejects.toMatchObject({
      status: 502,
      message: 'El servidor respondió en un formato inesperado.',
    })
  })

  it('me() devuelve el usuario de la sesión', async () => {
    restore = mockApi(() => ({ status: 200, data: USER_DTO }))

    await expect(authApi.me()).resolves.toMatchObject({ fullName: 'Admin Demo' })
  })

  it('credenciales incorrectas llegan como ApiError 401 con el mensaje del servidor', async () => {
    restore = mockApi(() => ({
      status: 401,
      data: { title: 'No autorizado', status: 401, detail: 'Email o contraseña incorrectos' },
    }))

    const error = await authApi.login({ email: 'a@b.co', password: 'mala' }).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).message).toBe('Email o contraseña incorrectos')
  })
})
