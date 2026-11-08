import { describe, expect, it } from 'vitest'

import type { Permission } from '@/shared/auth/types'

import { initials } from './layouts/initials'
import { APP_NAVIGATION, filterNavigation, navItemPath } from './navigation'

const allow = (granted: Permission[]) => (permission: Permission) => granted.includes(permission)

describe('navigation', () => {
  it('cada módulo tiene un segmento único (no hay dos rutas iguales)', () => {
    const segments = APP_NAVIGATION.map((item) => item.segment)

    expect(new Set(segments).size).toBe(segments.length)
  })

  it('construye las URLs bajo /app', () => {
    const [home, vehicles] = APP_NAVIGATION

    expect(navItemPath(home)).toBe('/app')
    expect(navItemPath(vehicles)).toBe('/app/vehicles')
  })

  it('un visualizador sin users:read NO ve "Usuarios" ni "Auditoría"', () => {
    const viewer = allow(['dashboard:read', 'vehicles:read'])

    const labels = filterNavigation(APP_NAVIGATION, viewer).map((item) => item.label)

    expect(labels).toEqual(['Resumen', 'Vehículos'])
  })

  it('no modifica la lista original (inmutabilidad)', () => {
    const before = APP_NAVIGATION.length

    filterNavigation(APP_NAVIGATION, allow([]))

    expect(APP_NAVIGATION).toHaveLength(before)
  })
})

describe('initials', () => {
  it.each([
    ['Ana María Gómez', 'AM'],
    ['  administrador  ', 'A'],
    ['', ''],
  ])('"%s" -> "%s"', (name, expected) => {
    expect(initials(name)).toBe(expected)
  })
})
