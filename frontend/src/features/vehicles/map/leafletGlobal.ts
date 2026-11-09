/**
 * leaflet.markercluster es un plugin "clásico": se engancha a la variable GLOBAL `L`.
 * Este módulo la publica ANTES de cargar el plugin (los imports se evalúan en orden).
 */
import L from 'leaflet'

declare global {
  interface Window {
    L: typeof L
  }
}

window.L = L

export default L
