/**
 * Detalle de vehículo (RF-12, RF-13, RF-09): datos transformados, posición, estado,
 * conductor vinculado (o "Sin conductor asignado"), pasajeros y campos personalizados.
 */
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { ApiError } from '@/shared/api/problem'
import { formatDateTime, formatRelative, formatSpeed, toCardinal } from '@/shared/format'
import { Button } from '@/shared/ui/Button'
import { EmptyState } from '@/shared/ui/EmptyState'

import { VehicleStatusBadge } from './components/VehicleStatusBadge'
import { fleetApi, fleetKeys, POSITIONS_REFRESH_MS } from './fleetApi'
import { FleetMap } from './map/FleetMap'
import './vehicles.css'

export function VehicleDetailPage() {
  const id = Number(useParams().vehicleId)
  const vehicle = useQuery({
    queryKey: fleetKeys.vehicle(id),
    queryFn: () => fleetApi.vehicle(id),
    enabled: Number.isInteger(id),
    refetchInterval: POSITIONS_REFRESH_MS,
  })

  if (vehicle.isPending) return <p className="ui-page-status" role="status">Cargando vehículo…</p>

  if (vehicle.isError) {
    const notFound = vehicle.error instanceof ApiError && vehicle.error.status === 404
    return (
      <div className="page-card">
        <EmptyState
          title={notFound ? 'Vehículo no encontrado' : 'No se pudo cargar el vehículo'}
          description={vehicle.error instanceof Error ? vehicle.error.message : undefined}
          action={notFound ? <Link to="/app/vehicles">Volver a vehículos</Link> : <Button onClick={() => void vehicle.refetch()}>Reintentar</Button>}
        />
      </div>
    )
  }

  const v = vehicle.data
  const p = v.position

  return (
    <section aria-labelledby="page-title">
      <header className="page-header">
        <p className="page-eyebrow">
          <Link to="/app/vehicles">Vehículos</Link> / Detalle
        </p>
        <h1 id="page-title" className="page-title">
          {v.name}
        </h1>
        <VehicleStatusBadge status={v.status} />
      </header>

      <div className="vehicle-detail">
        <article className="page-card" aria-labelledby="pos-title">
          <h2 id="pos-title" className="vehicle-detail__title">
            Posición
          </h2>
          {p ? (
            <>
              <dl className="vehicle-facts">
                <dt>Velocidad</dt>
                <dd>{formatSpeed(p.speedKmh)}</dd>
                <dt>Rumbo</dt>
                <dd>
                  {toCardinal(p.headingDeg)} ({p.headingDeg}°)
                </dd>
                <dt>Coordenadas</dt>
                <dd>
                  {p.latitude.toFixed(5)}, {p.longitude.toFixed(5)}
                </dd>
                <dt>Último reporte</dt>
                <dd>
                  {formatDateTime(p.recordedAt)} ({formatRelative(p.recordedAt)})
                </dd>
              </dl>
              <div className="vehicle-detail__map">
                <FleetMap
                  label={`Ubicación de ${v.name}`}
                  cluster={false}
                  compact
                  vehicles={[
                    {
                      id: v.id,
                      name: v.name,
                      status: v.status,
                      latitude: p.latitude,
                      longitude: p.longitude,
                      speedKmh: p.speedKmh,
                      headingDeg: p.headingDeg,
                      recordedAt: p.recordedAt,
                      driverName: v.driver?.name ?? null,
                    },
                  ]}
                />
              </div>
            </>
          ) : (
            <EmptyState title="Sin posición" description="Esta unidad nunca reportó una posición válida." />
          )}
        </article>

        <article className="page-card" aria-labelledby="driver-title">
          <h2 id="driver-title" className="vehicle-detail__title">
            Conductor
          </h2>
          {v.driver ? (
            <dl className="vehicle-facts">
              <dt>Nombre</dt>
              <dd>{v.driver.name}</dd>
              <dt>Código</dt>
              <dd>{v.driver.code || '—'}</dd>
              <dt>Teléfono</dt>
              <dd>{v.driver.phone || '—'}</dd>
            </dl>
          ) : (
            <EmptyState
              title="Sin conductor asignado"
              description="Este vehículo no tiene un conductor vinculado en Wialon."
            />
          )}
        </article>

        <article className="page-card" aria-labelledby="passengers-title">
          <h2 id="passengers-title" className="vehicle-detail__title">
            Pasajeros asignados ({v.passengers.length})
          </h2>
          {v.passengers.length ? (
            <ul className="vehicle-list">
              {v.passengers.map((passenger) => (
                <li key={passenger.id}>
                  <span>{passenger.name}</span>
                  <span className="vehicles-muted">{passenger.code || 'sin código'}</span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title="Sin pasajeros" description="No hay pasajeros asignados a este vehículo." />
          )}
        </article>

        <article className="page-card" aria-labelledby="fields-title">
          <h2 id="fields-title" className="vehicle-detail__title">
            Campos personalizados
          </h2>
          {v.customFields.length ? (
            <dl className="vehicle-facts">
              {v.customFields.map((field) => (
                <div key={field.id} style={{ display: 'contents' }}>
                  <dt>{field.name}</dt>
                  <dd>{field.value || '—'}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <EmptyState title="Sin campos personalizados" description="Esta unidad no tiene campos en Wialon." />
          )}
        </article>
      </div>
    </section>
  )
}
