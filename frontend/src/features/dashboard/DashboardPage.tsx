/**
 * Dashboard (RF-23): lo primero que se ve al entrar.
 *
 * - Banda de bienvenida con saludo según la hora de Bogotá e indicador "En vivo".
 * - 6 KPIs con ícono, color semántico, conteo animado y proporción sobre la flota.
 * - Mapa en vivo + "Últimos reportes" (los datos reales, no solo números).
 * - 2 visualizaciones: dona por estado y barras con/sin conductor (+ conclusión en texto).
 * Todo se refresca solo (KPIs 30 s, posiciones 15 s) y se pausa con la pestaña oculta.
 * Las animaciones respetan prefers-reduced-motion.
 */
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'

import { fleetApi, fleetKeys, POSITIONS_REFRESH_MS } from '@/features/vehicles/fleetApi'
import { FleetMap } from '@/features/vehicles/map/FleetMap'
import { VEHICLE_STATUS_PRESENTATION } from '@/features/vehicles/vehicleStatus'
import { useAuth } from '@/shared/auth/useAuth'
import { formatDateTime, formatRelative } from '@/shared/format'
import { Button } from '@/shared/ui/Button'
import { ButtonLink } from '@/shared/ui/ButtonLink'
import { BarChart, DonutChart } from '@/shared/ui/charts'
import { EmptyState } from '@/shared/ui/EmptyState'

import { DriverIcon, FleetIcon, MovingIcon, OfflineIcon, PassengersIcon, StoppedIcon } from './DashboardIcons'
import { KpiCard } from './KpiCard'
import { RecentReports } from './RecentReports'
import './dashboard.css'

const REFRESH_MS = 30_000
const STATUS_COLORS = {
  moving: 'var(--color-success)',
  stopped: 'var(--palette-red-dark)',
  offline: 'var(--palette-gray)',
} as const

const percentFormat = new Intl.NumberFormat('es-CO', { style: 'percent', maximumFractionDigits: 0 })

/** "85 %": la conclusión del gráfico en texto (no depender solo del color ni de leer el gráfico). */
function percent(part: number, total: number): string {
  return percentFormat.format(total ? part / total : 0)
}

const hourInBogota = () =>
  Number(new Intl.DateTimeFormat('es-CO', { hour: 'numeric', hour12: false, timeZone: 'America/Bogota' }).format(new Date()))

function greeting(): string {
  const hour = hourInBogota() % 24 // algunos motores devuelven 24 a medianoche
  if (hour < 5) return 'Buenas noches' // madrugada: lo natural sigue siendo "noches"
  if (hour < 12) return 'Buenos días'
  if (hour < 19) return 'Buenas tardes'
  return 'Buenas noches'
}

export function DashboardPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const summary = useQuery({ queryKey: fleetKeys.summary, queryFn: fleetApi.summary, refetchInterval: REFRESH_MS })
  const positions = useQuery({
    queryKey: fleetKeys.positions,
    queryFn: fleetApi.positions,
    refetchInterval: POSITIONS_REFRESH_MS,
  })
  const firstName = user?.fullName.split(' ')[0] ?? ''

  return (
    <section aria-labelledby="page-title" className="dashboard">
      <header className="welcome">
        <div className="welcome__text">
          <p className="welcome__live">
            <span className="welcome__dot" aria-hidden="true" /> En vivo
            {summary.data && <> · actualizado {formatRelative(summary.data.generatedAt)}</>}
          </p>
          <h1 id="page-title" className="welcome__title">
            {greeting()}, {firstName}
          </h1>
          <p className="welcome__subtitle">
            {summary.data
              ? `${summary.data.byStatus.moving + summary.data.byStatus.stopped} de ${summary.data.totalVehicles} vehículos reportando ahora mismo.`
              : 'Este es el estado de tu flota en tiempo real.'}
          </p>
        </div>
        <ButtonLink to="/app/vehicles" variant="primary">
          Ver mapa de flota
        </ButtonLink>
      </header>

      {summary.isPending && (
        <div className="kpi-grid" role="status" aria-label="Cargando indicadores">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="kpi kpi--skeleton" aria-hidden="true">
              <span className="ui-skeleton" style={{ inlineSize: '60%' }} />
              <span className="ui-skeleton kpi__skeleton-value" />
            </div>
          ))}
        </div>
      )}

      {summary.isError && (
        <div className="page-card">
          <EmptyState
            title="No se pudieron cargar los indicadores"
            description={summary.error instanceof Error ? summary.error.message : 'Inténtalo de nuevo.'}
            action={<Button onClick={() => void summary.refetch()}>Reintentar</Button>}
          />
        </div>
      )}

      {summary.data && (
        <>
          <dl className="kpi-grid">
            <KpiCard index={0} tone="brand" label="Vehículos" value={summary.data.totalVehicles} icon={<FleetIcon />} />
            {(
              [
                ['moving', <MovingIcon key="m" />],
                ['stopped', <StoppedIcon key="s" />],
                ['offline', <OfflineIcon key="o" />],
              ] as const
            ).map(([status, icon], i) => (
              <KpiCard
                key={status}
                index={i + 1}
                tone={status}
                label={VEHICLE_STATUS_PRESENTATION[status].label}
                value={summary.data.byStatus[status]}
                icon={icon}
                share={{ part: summary.data.byStatus[status], total: summary.data.totalVehicles }}
              />
            ))}
            <KpiCard index={4} tone="neutral" label="Conductores" value={summary.data.totalDrivers} icon={<DriverIcon />} />
            <KpiCard index={5} tone="neutral" label="Pasajeros" value={summary.data.totalPassengers} icon={<PassengersIcon />} />
          </dl>

          <div className="dashboard-live">
            <article className="page-card dashboard-live__map" aria-labelledby="live-map-title">
              <div className="dashboard-card-head">
                <h2 id="live-map-title" className="dashboard-chart-title">
                  Mapa en vivo
                </h2>
                <span className="dashboard-card-head__meta">{positions.data?.length ?? 0} con posición</span>
              </div>
              <FleetMap
                label="Mapa en vivo de la flota"
                vehicles={positions.data ?? []}
                onOpenDetail={(id) => void navigate(`/app/vehicles/${id}`)}
              />
            </article>
            <article className="page-card" aria-labelledby="recent-title">
              <div className="dashboard-card-head">
                <h2 id="recent-title" className="dashboard-chart-title">
                  Últimos reportes
                </h2>
              </div>
              {positions.data ? (
                <RecentReports points={positions.data} />
              ) : (
                <p className="ui-page-status" role="status">
                  Cargando…
                </p>
              )}
            </article>
          </div>

          <div className="dashboard-charts">
            <article className="page-card" aria-labelledby="chart-status">
              <h2 id="chart-status" className="dashboard-chart-title">
                Vehículos por estado
              </h2>
              <DonutChart
                title="Vehículos por estado"
                segments={(['moving', 'stopped', 'offline'] as const).map((status) => ({
                  label: VEHICLE_STATUS_PRESENTATION[status].label,
                  value: summary.data.byStatus[status],
                  color: STATUS_COLORS[status],
                }))}
              />
              <p className="dashboard-insight">
                {percent(summary.data.byStatus.moving + summary.data.byStatus.stopped, summary.data.totalVehicles)} de
                la flota reportó en los últimos 30 minutos.
              </p>
            </article>
            <article className="page-card" aria-labelledby="chart-drivers">
              <h2 id="chart-drivers" className="dashboard-chart-title">
                Asignación de conductores
              </h2>
              <BarChart
                title="Vehículos con y sin conductor asignado"
                segments={[
                  { label: 'Con conductor', value: summary.data.withDriver, color: 'var(--color-success)' },
                  { label: 'Sin conductor', value: summary.data.withoutDriver, color: 'var(--palette-red)' },
                ]}
              />
              <p className="dashboard-insight">
                <strong>{summary.data.withoutDriver}</strong> de {summary.data.totalVehicles} vehículos (
                {percent(summary.data.withoutDriver, summary.data.totalVehicles)}) no tienen conductor asignado.
              </p>
            </article>
          </div>

          <p className="dashboard-footnote">
            Datos de Wialon · {formatDateTime(summary.data.generatedAt)} (hora Colombia) · se actualiza solo.
          </p>
        </>
      )}
    </section>
  )
}
