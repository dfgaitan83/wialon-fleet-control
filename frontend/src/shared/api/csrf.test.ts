import { afterEach, describe, expect, it } from 'vitest'

import { clearCsrfCookie, setCsrfCookie } from '@/test/cookies'

import { hasSessionHint, needsCsrf, readCookie } from './csrf'

describe('csrf', () => {
  afterEach(() => clearCsrfCookie())

  it('lee la cookie CSRF y detecta el indicio de sesión', () => {
    expect(hasSessionHint()).toBe(false)

    setCsrfCookie('abc%3D') // valor codificado como lo envía el servidor

    expect(readCookie('fleet_csrf')).toBe('abc=')
    expect(hasSessionHint()).toBe(true)
  })

  it.each([
    ['post', true],
    ['PUT', true],
    ['patch', true],
    ['delete', true],
    ['get', false],
    ['HEAD', false],
    [undefined, false], // axios usa GET por defecto
  ])('needsCsrf(%s) = %s', (method, expected) => {
    expect(needsCsrf(method)).toBe(expected)
  })
})
