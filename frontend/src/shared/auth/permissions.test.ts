import { describe, expect, it } from 'vitest'

import { authUser } from '@/test/users'

import { userHasPermission } from './permissions'

describe('userHasPermission', () => {
  it('sin sesión no hay ningún permiso', () => {
    expect(userHasPermission(null, 'vehicles:read')).toBe(false)
  })

  it('concede solo los permisos que el usuario tiene', () => {
    const operator = authUser(['vehicles:read'])

    expect(userHasPermission(operator, 'vehicles:read')).toBe(true)
    expect(userHasPermission(operator, 'drivers:write')).toBe(false)
  })

  it('no existe comodín: "*:*" ya no concede nada (el backend envía permisos explícitos)', () => {
    expect(userHasPermission(authUser(['*:*']), 'users:write')).toBe(false)
  })
})
