import { describe, expect, it } from 'vitest'

import { bogotaInputToDate, dateToBogotaInput } from './bogotaTime'

describe('bogotaTime', () => {
  it('interpreta el input en hora de Bogotá (UTC-5)', () => {
    expect(bogotaInputToDate('2026-11-08T07:30')?.toISOString()).toBe('2026-11-08T12:30:00.000Z')
  })

  it('rechaza textos inválidos', () => {
    expect(bogotaInputToDate('')).toBeNull()
    expect(bogotaInputToDate('2026-13-40T99:99')).toBeNull()
  })

  it('ida y vuelta sin perder minutos', () => {
    const date = new Date('2026-11-09T03:15:00Z')
    expect(dateToBogotaInput(date)).toBe('2026-11-08T22:15')
    expect(bogotaInputToDate(dateToBogotaInput(date))).toEqual(date)
  })
})
