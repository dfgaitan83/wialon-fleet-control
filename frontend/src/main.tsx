/**
 * Punto de entrada del navegador: monta la app en <div id="root"> de index.html.
 */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'

import { AppProviders } from '@/app/providers'
import { router } from '@/app/router'
import '@/shared/ui/styles/global.css' // reset + tokens: se carga UNA sola vez aquí

const rootElement = document.getElementById('root')
// Falla rápido y claro si index.html no tiene el contenedor (en vez de un "null" críptico).
if (rootElement === null) throw new Error('No se encontró el elemento #root en index.html')

createRoot(rootElement).render(
  // StrictMode: en desarrollo ejecuta dos veces efectos para detectar efectos mal limpiados.
  <StrictMode>
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  </StrictMode>,
)
