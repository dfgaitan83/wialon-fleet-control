/**
 * Mapa del recorrido: polilínea completa + marcador del punto actual del playback.
 * Imperativo dentro de useEffect (Leaflet maneja su propio DOM). El mapa se crea
 * UNA vez; la polilínea se rehace solo cuando cambia el recorrido y el marcador
 * solo se mueve (setLatLng) en cada paso: barato aunque haya 2000 puntos.
 */
import 'leaflet/dist/leaflet.css'

import L from 'leaflet'
import { useEffect, useRef } from 'react'

import type { TrackPoint } from './historyApi'

const OSM_TILES = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
const OSM_ATTRIBUTION = '&copy; OpenStreetMap'
const COLOMBIA_CENTER: L.LatLngTuple = [4.6, -74.08]
const ROUTE_COLOR = '#1E8C93' // teal de la paleta obligatoria
const START_COLOR = '#1E8C93'
const END_COLOR = '#A81A2B'

interface TrackMapProps {
  readonly points: readonly TrackPoint[]
  readonly current: TrackPoint | null
}

const dot = (color: string) =>
  L.divIcon({
    className: 'track-dot',
    html: `<span style="background:${color}"></span>`,
    iconSize: [14, 14],
  })

export function TrackMap({ points, current }: TrackMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const routeRef = useRef<L.LayerGroup | null>(null)
  const cursorRef = useRef<L.CircleMarker | null>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const map = L.map(containerRef.current, { center: COLOMBIA_CENTER, zoom: 6 })
    L.tileLayer(OSM_TILES, { attribution: OSM_ATTRIBUTION, maxZoom: 19 }).addTo(map)
    routeRef.current = L.layerGroup().addTo(map)
    mapRef.current = map
    return () => {
      map.remove()
      mapRef.current = null
      cursorRef.current = null
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    const route = routeRef.current
    if (!map || !route) return
    route.clearLayers()
    cursorRef.current = null
    if (points.length === 0) return
    const latLngs = points.map((p): L.LatLngTuple => [p.latitude, p.longitude])
    const line = L.polyline(latLngs, { color: ROUTE_COLOR, weight: 4, opacity: 0.85 }).addTo(route)
    L.marker(latLngs[0], { icon: dot(START_COLOR), title: 'Inicio' }).addTo(route)
    L.marker(latLngs[latLngs.length - 1], { icon: dot(END_COLOR), title: 'Fin' }).addTo(route)
    map.fitBounds(line.getBounds(), { padding: [24, 24], maxZoom: 16 })
  }, [points])

  useEffect(() => {
    const route = routeRef.current
    if (!route || !current) return
    const latLng: L.LatLngTuple = [current.latitude, current.longitude]
    if (cursorRef.current) {
      cursorRef.current.setLatLng(latLng)
    } else {
      cursorRef.current = L.circleMarker(latLng, {
        radius: 9,
        color: '#fff',
        weight: 3,
        fillColor: '#EB162C',
        fillOpacity: 1,
      }).addTo(route)
    }
  }, [current, points])

  return <div ref={containerRef} className="track-map" role="region" aria-label="Mapa del recorrido" />
}
