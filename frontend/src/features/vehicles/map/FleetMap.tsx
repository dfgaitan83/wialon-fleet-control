/**
 * Mapa de flota (RF-11, RF-15): Leaflet + OpenStreetMap (gratis, sin tarjeta; se
 * respeta la atribución), agrupación de marcadores (clustering) e ícono por estado.
 *
 * - Imperativo dentro de useEffect: Leaflet manipula el DOM por su cuenta; React
 *   solo le pasa datos (puntos, seleccionado) y recibe eventos (onSelect).
 * - SEGURIDAD (SEG-03): el popup se construye con nodos DOM y textContent, NUNCA
 *   con innerHTML. Los nombres vienen de Wialon (cuenta compartida): un nombre
 *   malicioso como "<img onerror=...>" se mostraría como texto, sin ejecutarse.
 * - Sincronización lista↔mapa: si cambia `selectedId`, el mapa hace zoom hasta el
 *   marcador (sacándolo del cluster) y abre su popup.
 */
import 'leaflet/dist/leaflet.css'
import './leafletGlobal'
import 'leaflet.markercluster'
import 'leaflet.markercluster/dist/MarkerCluster.css'
import 'leaflet.markercluster/dist/MarkerCluster.Default.css'
import './map.css'

import L from 'leaflet'
import { useEffect, useRef } from 'react'

import { VEHICLE_STATUS_PRESENTATION, type VehicleStatus } from '../vehicleStatus'
import { formatDateTime, formatSpeed, toCardinal } from '@/shared/format'

export interface MapVehicle {
  readonly id: number
  readonly name: string
  readonly status: VehicleStatus
  readonly latitude: number
  readonly longitude: number
  readonly speedKmh: number
  readonly headingDeg: number
  readonly recordedAt: Date
  readonly driverName: string | null
}

interface FleetMapProps {
  readonly vehicles: readonly MapVehicle[]
  readonly selectedId?: number | null
  readonly onSelect?: (id: number) => void
  readonly onOpenDetail?: (id: number) => void
  readonly label: string // nombre accesible del mapa
  readonly cluster?: boolean
  readonly compact?: boolean // versión baja (detalle de vehículo)
}

const COLOMBIA_CENTER: L.LatLngTuple = [4.6, -74.08]
const OSM_TILES = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
const OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'

function markerIcon(status: VehicleStatus, selected: boolean): L.DivIcon {
  return L.divIcon({
    className: `fleet-marker fleet-marker--${status}${selected ? ' fleet-marker--selected' : ''}`,
    iconSize: selected ? [26, 26] : [18, 18],
    html: '', // sin HTML: la forma y el color los pone el CSS
  })
}

/** Popup con nodos DOM + textContent (anti-XSS). */
function popupContent(vehicle: MapVehicle, onOpenDetail?: (id: number) => void): HTMLElement {
  const root = document.createElement('div')
  root.className = 'fleet-popup'
  const line = (text: string, className?: string) => {
    const element = document.createElement('p')
    element.textContent = text
    if (className) element.className = className
    root.append(element)
  }
  line(vehicle.name, 'fleet-popup__title')
  line(VEHICLE_STATUS_PRESENTATION[vehicle.status].label, 'fleet-popup__status')
  line(`${formatSpeed(vehicle.speedKmh)} · rumbo ${toCardinal(vehicle.headingDeg)}`)
  line(`Conductor: ${vehicle.driverName ?? 'Sin conductor asignado'}`)
  line(`Último reporte: ${formatDateTime(vehicle.recordedAt)}`)
  if (onOpenDetail) {
    const button = document.createElement('button')
    button.type = 'button'
    button.className = 'fleet-popup__link'
    button.textContent = 'Ver detalle'
    button.addEventListener('click', () => onOpenDetail(vehicle.id))
    root.append(button)
  }
  return root
}

export function FleetMap({
  vehicles,
  selectedId = null,
  onSelect,
  onOpenDetail,
  label,
  cluster = true,
  compact = false,
}: FleetMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const layerRef = useRef<L.LayerGroup | null>(null)
  const markersRef = useRef(new Map<number, L.Marker>())
  const fittedRef = useRef(false) // encuadrar solo la primera vez (el polling no debe mover el mapa)
  // Los marcadores leen los handlers MÁS recientes sin recrear el mapa en cada render.
  const handlersRef = useRef({ onSelect, onOpenDetail })
  useEffect(() => {
    handlersRef.current = { onSelect, onOpenDetail }
  }, [onSelect, onOpenDetail])

  // 1) Crear el mapa una sola vez.
  useEffect(() => {
    if (!containerRef.current) return
    const map = L.map(containerRef.current, { center: COLOMBIA_CENTER, zoom: 6 })
    L.tileLayer(OSM_TILES, { attribution: OSM_ATTRIBUTION, maxZoom: 19 }).addTo(map)
    const layer = cluster ? L.markerClusterGroup({ showCoverageOnHover: false }) : L.layerGroup()
    layer.addTo(map)
    mapRef.current = map
    layerRef.current = layer
    const markers = markersRef.current // copia local: la limpieza usa el mismo objeto
    // Leaflet mide su contenedor al crearse; si la tarjeta crece después (p. ej. al cargar
    // otra columna), se recalcula para no dejar zonas grises sin teselas.
    // Mejora progresiva: sin ResizeObserver (navegadores antiguos, jsdom) el mapa funciona igual.
    const resizeObserver =
      typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(() => map.invalidateSize())
    resizeObserver?.observe(containerRef.current)
    return () => {
      resizeObserver?.disconnect()
      map.remove()
      mapRef.current = null
      markers.clear()
      fittedRef.current = false
    }
  }, [cluster])

  // 2) Pintar marcadores cada vez que llegan posiciones nuevas (polling).
  useEffect(() => {
    const map = mapRef.current
    const layer = layerRef.current
    if (!map || !layer) return
    layer.clearLayers()
    markersRef.current.clear()
    for (const vehicle of vehicles) {
      const marker = L.marker([vehicle.latitude, vehicle.longitude], {
        icon: markerIcon(vehicle.status, vehicle.id === selectedId),
        title: vehicle.name, // tooltip nativo y nombre accesible del marcador
        keyboard: true,
      })
      marker.bindPopup(() => popupContent(vehicle, handlersRef.current.onOpenDetail))
      marker.on('click', () => handlersRef.current.onSelect?.(vehicle.id))
      marker.addTo(layer)
      markersRef.current.set(vehicle.id, marker)
    }
    if (!fittedRef.current && vehicles.length > 0) {
      map.fitBounds(L.latLngBounds(vehicles.map((v) => [v.latitude, v.longitude])), { padding: [24, 24], maxZoom: 15 })
      fittedRef.current = true
    }
  }, [vehicles, selectedId])

  // 3) Selección desde la lista: llevar el mapa al vehículo y abrir su popup.
  useEffect(() => {
    if (selectedId === null) return
    const marker = markersRef.current.get(selectedId)
    const layer = layerRef.current
    if (!marker || !layer) return
    if (layer instanceof L.MarkerClusterGroup) layer.zoomToShowLayer(marker, () => marker.openPopup())
    else marker.openPopup()
  }, [selectedId, vehicles])

  return <div ref={containerRef} className={compact ? 'fleet-map fleet-map--compact' : 'fleet-map'} role="region" aria-label={label} />
}
