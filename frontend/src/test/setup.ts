// Se ejecuta antes de cada archivo de test (ver "setupFiles" en vite.config.ts).
import '@testing-library/jest-dom/vitest' // añade matchers: toBeInTheDocument, toHaveClass...

import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

import { createBackendWakeup } from '@/shared/server/backendWakeup'

// DEP-04 en tests: el detector de arranque en frío REAL haría pings de red con esperas
// de hasta 95 s. Aquí se sustituye por una instancia con el MISMO código pero un ping
// que responde 200 al instante y sin esperas. Los tests del detector usan la fábrica
// directamente (backendWakeup.test.ts) con pings y esperas controlados.
vi.mock('@/shared/server/backendStatus', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/shared/server/backendStatus')>()
  const { useSyncExternalStore } = await import('react')
  const backendWakeup = createBackendWakeup({ ping: async () => 200, sleep: async () => {} })
  return {
    ...original,
    backendWakeup,
    useBackendStatus: () => useSyncExternalStore(backendWakeup.subscribe, backendWakeup.getStatus),
  }
})

// Desmonta lo renderizado y limpia el almacenamiento tras cada test -> tests aislados.
afterEach(() => {
  cleanup()
  sessionStorage.clear()
})
