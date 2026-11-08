import { beforeEach, describe, expect, it } from 'vitest'

import { tokenStorage } from './tokenStorage'

describe('tokenStorage', () => {
  beforeEach(() => tokenStorage.clear())

  it('guarda y devuelve el token', () => {
    tokenStorage.set('jwt-1')

    expect(tokenStorage.get()).toBe('jwt-1')
  })

  it('usa sessionStorage (se borra al cerrar la pestaña) y NUNCA localStorage', () => {
    tokenStorage.set('jwt-1')

    expect(sessionStorage.getItem('wfc.access_token')).toBe('jwt-1')
    expect(localStorage.length).toBe(0)
  })

  it('clear() elimina el token de memoria y de sessionStorage', () => {
    tokenStorage.set('jwt-1')

    tokenStorage.clear()

    expect(tokenStorage.get()).toBeNull()
    expect(sessionStorage.getItem('wfc.access_token')).toBeNull()
  })
})
