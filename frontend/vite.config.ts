/// <reference types="vitest/config" />
// La línea de arriba añade los tipos de la sección "test" (Vitest) a defineConfig.
import { fileURLToPath, URL } from 'node:url'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    // Alias "@/..." -> "src/...": imports cortos y estables, sin "../../../".
    // Debe coincidir con "paths" de tsconfig.app.json para que TypeScript lo entienda.
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    // Desarrollo: "/api" se reenvía al backend local. El navegador ve UN solo origen
    // (localhost:5173), igual que en producción con el rewrite de Vercel: las cookies
    // de sesión funcionan sin CORS y con SameSite.
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: false } },
  },
  test: {
    environment: 'jsdom', // simula el DOM del navegador para probar componentes React
    globals: false, // imports explícitos (describe, it, expect) -> más claro qué viene de Vitest
    setupFiles: ['./src/test/setup.ts'], // matchers como toBeInTheDocument()
    css: false, // los tests verifican comportamiento, no estilos
    coverage: {
      provider: 'v8',
      include: ['src/shared/**'], // por ahora medimos la capa compartida
      exclude: ['src/**/*.test.{ts,tsx}', 'src/**/index.ts'],
    },
  },
})
