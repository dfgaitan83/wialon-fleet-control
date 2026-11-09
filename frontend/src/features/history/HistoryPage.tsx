/**
 * Historial de recorridos (RF-24): elegir vehículo y rango (hora de Bogotá), ver el
 * recorrido en el mapa con estadísticas y reproducirlo punto a punto (playback).
 * El rango se valida aquí (UX inmediata) Y en el backend (la regla de verdad).
 */
import { useQuery } from '@tanstack/react-query'
import { type FormEvent, type ReactNode, useMemo, useState } from 'react'

import { formatDateTime, formatSpeed, toCardinal } from '@/shared/format'
import { Button } from '@/shared/ui/Button'
import { EmptyState } from '@/shared/ui/EmptyState'

import { fleetApi, fleetKeys } from '../vehicles/fleetApi'
import { bogotaInputToDate, dateToBogotaInput } from './bogotaTime'
import { historyApi, historyKeys, type Track, type TrackQuery } from './historyApi'
import { TrackMap } from './TrackMap'
import { PLAYBACK_SPEEDS, usePlayback } from './usePlayback'
import './history.css'

const MAX_RANGE_DAYS = 7
const DAY_MS = 86_400_000
const DEFAULT_RANGE_MS = DAY_MS // por defecto: últimas 24 h
const TRACK_STALE_MS = 5 * 60_000 // el pasado no cambia: no se vuelve a pedir al volver a la pestaña

const numberFormat = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 1 })

function validateRange(from: Date | null, to: Date | null, now: Date = new Date()): string | null {
  if (!from || !to) return 'Indica fecha y hora de inicio y de fin.'
  if (from >= to) return 'La fecha inicial debe ser anterior a la final.'
  if (to.getTime() - from.getTime() > MAX_RANGE_DAYS * DAY_MS) return `El rango máximo es de ${MAX_RANGE_DAYS} días.`
  if (from > now) return 'La fecha inicial no puede estar en el futuro.'
  return null
}

function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = Math.round(minutes % 60)
  return h > 0 ? `${h} h ${m} min` : `${m} min`
}

export function HistoryPage() {
  const vehicles = useQuery({ queryKey: fleetKeys.positions, queryFn: fleetApi.positions })
  const sortedVehicles = useMemo(
    () => [...(vehicles.data ?? [])].sort((a, b) => a.name.localeCompare(b.name, 'es')),
    [vehicles.data],
  )

  const [initialTo] = useState(() => new Date())
  const [formError, setFormError] = useState<string | null>(null)
  const [query, setQuery] = useState<TrackQuery | null>(null)

  const track = useQuery({
    queryKey: query ? historyKeys.track(query) : ['history', 'idle'],
    queryFn: () => historyApi.track(query as TrackQuery),
    enabled: query !== null,
    staleTime: TRACK_STALE_MS,
  })

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const vehicleId = Number(form.get('vehicle'))
    const from = bogotaInputToDate(String(form.get('from') ?? ''))
    const to = bogotaInputToDate(String(form.get('to') ?? ''))
    const error = vehicleId ? validateRange(from, to) : 'Selecciona un vehículo.'
    setFormError(error)
    if (!error && from && to) setQuery({ vehicleId, from, to })
  }

  let result: ReactNode
  if (query === null) {
    result = (
      <div className="page-card">
        <EmptyState title="Elige un vehículo y un rango" description={`Máximo ${MAX_RANGE_DAYS} días por consulta.`} />
      </div>
    )
  } else if (track.isPending) {
    result = (
      <p className="ui-page-status" role="status">
        Cargando recorrido…
      </p>
    )
  } else if (track.isError) {
    result = (
      <div className="page-card">
        <EmptyState
          title="No se pudo cargar el recorrido"
          description={track.error instanceof Error ? track.error.message : undefined}
          action={<Button onClick={() => void track.refetch()}>Reintentar</Button>}
        />
      </div>
    )
  } else if (track.data.points.length === 0) {
    result = (
      <div className="page-card">
        <EmptyState
          title="Sin recorrido en ese rango"
          description="El vehículo no reportó posiciones entre esas fechas. Prueba con otro rango."
        />
      </div>
    )
  } else {
    // key: un recorrido nuevo monta un reproductor nuevo (vuelve al inicio en pausa).
    result = <TrackViewer key={historyKeys.track(query).join('|')} track={track.data} />
  }

  return (
    <section aria-labelledby="page-title">
      <header className="page-header">
        <p className="page-eyebrow">Recorridos</p>
        <h1 id="page-title" className="page-title">
          Historial
        </h1>
      </header>

      <form className="page-card history-form" onSubmit={onSubmit} noValidate>
        <div className="ui-field history-form__vehicle">
          <label htmlFor="history-vehicle" className="ui-field__label">
            Vehículo
          </label>
          <select id="history-vehicle" name="vehicle" className="ui-field__input" defaultValue="" disabled={vehicles.isPending}>
            <option value="">{vehicles.isPending ? 'Cargando vehículos…' : 'Selecciona un vehículo'}</option>
            {sortedVehicles.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
          </select>
        </div>
        <div className="ui-field">
          <label htmlFor="history-from" className="ui-field__label">
            Desde (hora Bogotá)
          </label>
          <input
            id="history-from"
            name="from"
            type="datetime-local"
            className="ui-field__input"
            defaultValue={dateToBogotaInput(new Date(initialTo.getTime() - DEFAULT_RANGE_MS))}
          />
        </div>
        <div className="ui-field">
          <label htmlFor="history-to" className="ui-field__label">
            Hasta (hora Bogotá)
          </label>
          <input id="history-to" name="to" type="datetime-local" className="ui-field__input" defaultValue={dateToBogotaInput(initialTo)} />
        </div>
        <div className="history-form__actions">
          <Button type="submit" disabled={track.isFetching}>
            {track.isFetching ? 'Consultando…' : 'Ver recorrido'}
          </Button>
        </div>
        {formError && (
          <p role="alert" className="ui-field__error history-form__error">
            {formError}
          </p>
        )}
        {vehicles.isError && (
          <p role="alert" className="ui-field__error history-form__error">
            No se pudo cargar la lista de vehículos.
          </p>
        )}
      </form>

      {result}
    </section>
  )
}

function TrackViewer({ track }: { readonly track: Track }) {
  const { points } = track
  const playback = usePlayback(points.length)
  const current = points[playback.index] ?? null

  return (
    <div className="history-layout">
      <div className="page-card history-map-card">
        <TrackMap points={points} current={current} />
      </div>
      <aside className="history-side">
        <dl className="page-card history-stats" aria-label="Resumen del recorrido">
          <div>
            <dt>Distancia</dt>
            <dd>{numberFormat.format(track.distanceKm)} km</dd>
          </div>
          <div>
            <dt>Vel. máxima</dt>
            <dd>{formatSpeed(track.maxSpeedKmh)}</dd>
          </div>
          <div>
            <dt>En movimiento</dt>
            <dd>{formatDuration(track.movingMinutes)}</dd>
          </div>
          <div>
            <dt>Reportes GPS</dt>
            <dd>{track.totalPoints.toLocaleString('es-CO')}</dd>
          </div>
        </dl>

        <div className="page-card history-player" role="group" aria-label="Reproducción del recorrido">
          <div className="history-player__controls">
            <Button onClick={playback.toggle} disabled={points.length < 2} aria-pressed={playback.isPlaying}>
              {playback.isPlaying ? 'Pausar' : 'Reproducir'}
            </Button>
            <div className="history-player__speeds" role="radiogroup" aria-label="Velocidad de reproducción">
              {PLAYBACK_SPEEDS.map((s) => (
                <button
                  key={s}
                  type="button"
                  role="radio"
                  aria-checked={playback.speed === s}
                  className="history-player__speed"
                  onClick={() => playback.setSpeed(s)}
                >
                  x{s}
                </button>
              ))}
            </div>
          </div>
          <label htmlFor="history-seek" className="ui-visually-hidden">
            Posición en el recorrido
          </label>
          <input
            id="history-seek"
            type="range"
            className="history-player__seek"
            min={0}
            max={points.length - 1}
            value={playback.index}
            onChange={(e) => playback.seek(Number(e.target.value))}
          />
          {current && (
            <dl className="history-player__now">
              <dt>Hora</dt>
              <dd>{formatDateTime(current.recordedAt)}</dd>
              <dt>Velocidad</dt>
              <dd>{formatSpeed(current.speedKmh)}</dd>
              <dt>Rumbo</dt>
              <dd>
                {toCardinal(current.headingDeg)} ({current.headingDeg}°)
              </dd>
              <dt>Coordenadas</dt>
              <dd>
                {current.latitude.toFixed(5)}, {current.longitude.toFixed(5)}
              </dd>
            </dl>
          )}
        </div>
      </aside>
    </div>
  )
}
