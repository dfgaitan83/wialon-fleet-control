import { describe, expect, it } from 'vitest'

import { userHasPermission } from './permissions'
import type { AuthUser, Permission } from './types'

function user(permissions: Permission[]): AuthUser {
  return { id: '1', email: 'a@b.co', fullName: 'Ana', permissions }
}

describe('userHasPermission', () => {
  it('sin sesión no hay ningún permiso', () => {
    expect(userHasPermission(null, 'vehicles:read')).toBe(false)
  })

  it('concede solo los permisos que el usuario tiene', () => {
    const operator = user(['vehicles:read'])

    expect(userHasPermission(operator, 'vehicles:read')).toBe(true)
    expect(userHasPermission(operator, 'drivers:write')).toBe(false)
  })

  it('el comodín *:* del administrador concede cualquier permiso', () => {
    expect(userHasPermission(user(['*:*']), 'users:write')).toBe(true)
  })
})
