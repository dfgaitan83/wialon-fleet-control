/**
 * Test de CONTRATO del puerto AuthService (Sustitución de Liskov, la "L" de SOLID).
 *
 * El MISMO conjunto de pruebas se ejecuta contra cada implementación. Si todas
 * pasan, cualquiera puede reemplazar a otra dentro de AuthProvider sin romperlo.
 */
import { afterEach, describe, expect, it } from 'vitest'

import { ApiError } from '@/shared/api/problem'
import { mockApi } from '@/test/mockAdapter'

import { authApi } from './authApi'
import { demoAuthService } from './demoAuthService'
import type { AuthService } from './types'

const VALID = { email: 'admin@demo.local', password: 'secreta' }
const USER_DTO = { id: 'x', email: VALID.email, full_name: 'Admin', permissions: ['*:*'] }

/** Prepara el entorno de cada implementación (la HTTP necesita una "red" simulada). */
const implementations: ReadonlyArray<[string, AuthService, () => () => void]> = [
  [
    'authApi (HTTP)',
    authApi,
    () =>
      mockApi((config) => {
        if (config.url === '/auth/me') return { status: 200, data: USER_DTO }
        const body = JSON.parse(String(config.data)) as { password?: string }
        return body.password
          ? { status: 200, data: { access_token: 'jwt', token_type: 'bearer', user: USER_DTO } }
          : { status: 401, data: { title: 'No autorizado', status: 401 } }
      }),
  ],
  ['demoAuthService (memoria)', demoAuthService, () => () => {}],
]

describe.each(implementations)('Contrato AuthService: %s', (_name, service, setup) => {
  let restore: () => void = () => {}
  afterEach(() => restore())

  it('login válido devuelve token no vacío y usuario con permisos', async () => {
    restore = setup()

    const result = await service.login(VALID)

    expect(result.accessToken).not.toBe('')
    expect(result.user.permissions.length).toBeGreaterThan(0)
  })

  it('login inválido rechaza con ApiError 401 (nunca con otro tipo de error)', async () => {
    restore = setup()

    const error = await service.login({ email: VALID.email, password: '' }).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(401)
  })

  it('me() devuelve un usuario con nombre visible', async () => {
    restore = setup()

    const user = await service.me()

    expect(user.fullName).not.toBe('')
  })
})
