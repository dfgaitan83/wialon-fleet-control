/**
 * Arranque en frío (DEP-04): reintentos con espera creciente, single-flight y estados.
 * El ping y las esperas son falsos: el test no duerme ni usa red.
 */
import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/shared/api/problem'

import { type BackendStatus, createBackendWakeup, WAKE_DELAYS_MS } from './backendWakeup'

/** Ping que devuelve, en orden, los códigos indicados (null = sin respuesta). */
function scriptedPing(...replies: Array<number | null>) {
  const queue = [...replies]
  return vi.fn(async () => (queue.length > 0 ? queue.shift()! : null))
}

describe('createBackendWakeup', () => {
  it('si el backend responde al primer ping queda listo sin esperar', async () => {
    const sleep = vi.fn<(ms: number) => Promise<void>>(async () => {})
    const wakeup = createBackendWakeup({ ping: scriptedPing(200), sleep })

    await wakeup.ensureReady()

    expect(wakeup.getStatus()).toBe('ready')
    expect(sleep).not.toHaveBeenCalled()
  })

  it('arranque en frío: pasa por "waking", espera 1, 2, 4 s... y queda listo', async () => {
    const sleep = vi.fn<(ms: number) => Promise<void>>(async () => {})
    const wakeup = createBackendWakeup({ ping: scriptedPing(null, 503, null, 200), sleep })
    const seen: BackendStatus[] = []
    wakeup.subscribe(() => seen.push(wakeup.getStatus()))

    await wakeup.ensureReady()

    expect(seen).toEqual(['checking', 'waking', 'ready'])
    expect(sleep.mock.calls.map(([ms]) => ms)).toEqual([1_000, 2_000, 4_000]) // backoff creciente
  })

  it('cualquier respuesta HTTP salvo 502/503/504 cuenta como despierto (incluso 401 o 404)', async () => {
    const wakeup = createBackendWakeup({ ping: scriptedPing(404), sleep: async () => {} })

    await wakeup.ensureReady()

    expect(wakeup.getStatus()).toBe('ready')
  })

  it('si se agota el tiempo queda en "down" y rechaza con un mensaje claro', async () => {
    const wakeup = createBackendWakeup({ ping: scriptedPing(), sleep: async () => {} }) // nunca responde

    const error = await wakeup.ensureReady().catch((e: unknown) => e)

    expect(wakeup.getStatus()).toBe('down')
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).message).toMatch(/no respondió a tiempo/)
  })

  it('el total de espera ronda los 90 s (lo que tarda un arranque en frío de Render)', () => {
    const totalSeconds = WAKE_DELAYS_MS.reduce((sum, ms) => sum + ms, 0) / 1000

    expect(totalSeconds).toBeGreaterThanOrEqual(90)
  })

  it('llamadas simultáneas comparten UN solo proceso de espera (single-flight)', async () => {
    const ping = scriptedPing(null, 200)
    const wakeup = createBackendWakeup({ ping, sleep: async () => {} })

    await Promise.all([wakeup.ensureReady(), wakeup.ensureReady(), wakeup.ensureReady()])

    expect(ping).toHaveBeenCalledTimes(2) // no 6
  })

  it('una vez listo no vuelve a hacer ping', async () => {
    const ping = scriptedPing(200)
    const wakeup = createBackendWakeup({ ping, sleep: async () => {} })
    await wakeup.ensureReady()

    await wakeup.ensureReady()

    expect(ping).toHaveBeenCalledOnce()
  })

  it('retry() tras "down" vuelve a intentarlo desde cero', async () => {
    const replies: Array<number | null> = [...Array(WAKE_DELAYS_MS.length + 1).fill(null), 200]
    const wakeup = createBackendWakeup({ ping: scriptedPing(...replies), sleep: async () => {} })
    await wakeup.ensureReady().catch(() => undefined)
    expect(wakeup.getStatus()).toBe('down')

    await wakeup.retry()

    expect(wakeup.getStatus()).toBe('ready')
  })
})
