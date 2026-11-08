// Se ejecuta antes de cada archivo de test (ver "setupFiles" en vite.config.ts).
import '@testing-library/jest-dom/vitest' // añade matchers: toBeInTheDocument, toHaveClass...

import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Desmonta lo renderizado y limpia el almacenamiento tras cada test -> tests aislados.
afterEach(() => {
  cleanup()
  sessionStorage.clear()
})
