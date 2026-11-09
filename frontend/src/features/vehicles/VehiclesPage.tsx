/**
 * Vehículos (RF-10, RF-11, RF-14, RF-15): lista + mapa sincronizados.
 *
 * - Lista con búsqueda, filtro por estado y paginación DEL SERVIDOR.
 * - Mapa con todos los vehículos con posición, clustering e ícono por estado.
 * - Seleccionar en la lista lleva el mapa al vehículo; clic en el mapa resalta la fila.
 * - Polling cada 15 s (RF-14): TanStack Query lo PAUSA cuando la pestaña no está visible.
 * - Móvil (UX-01): pestañas Lista / Mapa; desde 64rem se ven lado a lado.
 */
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { formatDateTime, formatRelative, formatSpeed, toCardinal } from '@/shared/format'
import { Button } from '@/shared/ui/Button'
import { DataTable, type DataTableColumn } from '@/shared/ui/DataTable'
import { EmptyState } from '@/shared/ui/EmptyState'

import { VehicleStatusBadge } from './components/VehicleStatusBadge'
import { fleetApi, fleetKeys, POSITIONS_REFRESH_MS, type VehicleQuery, type VehicleSummary } from './fleetApi'
import { FleetMap } from './map/FleetMap'
import { VEHICLE_STATUS_PRESENTATION, type VehicleStatus } from './vehicleStatus'
import './vehicles.css'

const PAGE_SIZE = 15
const STATUS_FILTERS: ReadonlyArray<VehicleStatus> = ['moving', 'stopped', 'offline']
type MobileView = 'list' | 'map'

export function VehiclesPage() {
  const navigate = useNavigate()
  const [query, setQuery] = useState<VehicleQuery>({ page: 1, pageSize: PAGE_SIZE, search: '', status: '' })
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [mobileView, setMobileView] = useState<MobileView>('list')

  const vehicles = useQuery({
    queryKey: fleetKeys.vehicles(query),
    queryFn: () => fleetApi.vehicles(query),
    placeholderData: keepPreviousData,
    refetchInterval: POSITIONS_REFRESH_MS,
  })
  const positions = useQuery({
    queryKey: fleetKeys.positions,
    queryFn: fleetApi.positions,
    refetchInterval: POSITIONS_REFRESH_MS,
  })
  const totalPages = Math.max(1, Math.ceil((vehicles.data?.total ?? 0) / PAGE_SIZE))
  const openDetail = (id: number) => void navigate(`/app/vehicles/${id}`)

  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    setQuery((q) => ({
      ...q,
      page: 1,
      search: String(form.get('q') ?? '').trim(),
      status: String(form.get('status') ?? '') as VehicleStatus | '',
    }))
  }

  const select = (id: number) => {
    setSelectedId(id)
    setMobileView('map') // en móvil, elegir en la lista lleva al mapa
  }

  const columns: DataTableColumn<VehicleSummary>[] = [
    {
      id: 'name',
      header: 'Vehículo',
      cell: (v) => (
        <span className="vehicles-name">
          <Link to={`/app/vehicles/${v.id}`} className="vehicles-name__link">
            {v.name}
          </Link>
          {v.position && (
            <button type="button" className="vehicles-name__locate" onClick={() => select(v.id)}>
              Ver en el mapa
            </button>
          )}
        </span>
      ),
    },
    { id: 'status', header: 'Estado', cell: (v) => <VehicleStatusBadge status={v.status} /> },
    {
      id: 'speed',
      header: 'Velocidad',
      align: 'end',
      numeric: true,
      cell: (v) => (v.position ? `${formatSpeed(v.position.speedKmh)} ${toCardinal(v.position.headingDeg)}` : '—'),
    },
    {
      id: 'driver',
      header: 'Conductor',
      cell: (v) => v.driver?.name ?? <span className="vehicles-muted">Sin conductor</span>,
    },
    {
      id: 'report',
      header: 'Último reporte',
      cell: (v) =>
        v.position ? (
          <time dateTime={v.position.recordedAt.toISOString()} title={formatDateTime(v.position.recordedAt)}>
            {formatRelative(v.position.recordedAt)}
          </time>
        ) : (
          <span className="vehicles-muted">Nunca reportó</span>
        ),
    },
  ]

  return (
    <section aria-labelledby="page-title">
      <header className="page-header">
        <p className="page-eyebrow">Panel de flota</p>
        <h1 id="page-title" className="page-title">
          Vehículos
        </h1>
        <p className="page-subtitle">Posiciones actualizadas cada 15 segundos.</p>
      </header>

      <form className="vehicles-toolbar page-card" role="search" onSubmit={handleSearch}>
        <label className="ui-visually-hidden" htmlFor="vehicles-q">
          Buscar vehículo o conductor
        </label>
        <input id="vehicles-q" name="q" className="ui-field__input" placeholder="Buscar vehículo o conductor" />
        <label className="ui-visually-hidden" htmlFor="vehicles-status">
          Filtrar por estado
        </label>
        <select id="vehicles-status" name="status" className="ui-field__input vehicles-toolbar__status" defaultValue="">
          <option value="">Todos los estados</option>
          {STATUS_FILTERS.map((s) => (
            <option key={s} value={s}>
              {VEHICLE_STATUS_PRESENTATION[s].label}
            </option>
          ))}
        </select>
        <Button type="submit" variant="primary">
          Aplicar
        </Button>
      </form>

      <div className="vehicles-tabs" role="tablist" aria-label="Vista">
        {(['list', 'map'] as const).map((view) => (
          <button
            key={view}
            type="button"
            role="tab"
            aria-selected={mobileView === view}
            className="vehicles-tabs__tab"
            onClick={() => setMobileView(view)}
          >
            {view === 'list' ? 'Lista' : 'Mapa'}
          </button>
        ))}
      </div>

      <div className="vehicles-layout" data-view={mobileView}>
        <div className="page-card vehicles-layout__list">
          {vehicles.isError ? (
            <EmptyState
              title="No se pudieron cargar los vehículos"
              description={vehicles.error instanceof Error ? vehicles.error.message : 'Inténtalo de nuevo.'}
              action={<Button onClick={() => void vehicles.refetch()}>Reintentar</Button>}
            />
          ) : (
            <DataTable
              caption="Vehículos de la flota"
              columns={columns}
              rows={vehicles.data?.items ?? []}
              getRowId={(v) => String(v.id)}
              isLoading={vehicles.isPending}
              selectedRowId={selectedId === null ? null : String(selectedId)}
              emptyState={
                <EmptyState
                  title="Ningún vehículo coincide"
                  description="Prueba con otro nombre o quita el filtro de estado."
                />
              }
            />
          )}
          <nav className="vehicles-pagination" aria-label="Paginación de vehículos">
            <Button size="sm" disabled={query.page <= 1} onClick={() => setQuery((q) => ({ ...q, page: q.page - 1 }))}>
              Anterior
            </Button>
            <span aria-live="polite">
              Página {query.page} de {totalPages} · {vehicles.data?.total ?? 0} vehículos
            </span>
            <Button
              size="sm"
              disabled={query.page >= totalPages}
              onClick={() => setQuery((q) => ({ ...q, page: q.page + 1 }))}
            >
              Siguiente
            </Button>
          </nav>
        </div>

        <div className="vehicles-layout__map">
          {positions.isError ? (
            <div className="page-card">
              <EmptyState title="No se pudo cargar el mapa" description="Reintentando automáticamente…" />
            </div>
          ) : (
            <FleetMap
              label="Mapa de vehículos"
              vehicles={positions.data ?? []}
              selectedId={selectedId}
              onSelect={setSelectedId}
              onOpenDetail={openDetail}
            />
          )}
        </div>
      </div>
    </section>
  )
}
