/**
 * Dashboard (RF-23): KPIs de la flota + 2 visualizaciones (dona por estado y barras
 * con/sin conductor). Los números los calcula el backend sobre la misma foto que la
 * lista de vehículos; se refrescan solos cada 30 s (pausado con la pestaña oculta).
 */
import { useQuery } from '@tanstack/react-query'

import { fleetApi, fleetKeys } from '@/features/vehicles/fleetApi'
import { VEHICLE_STATUS_PRESENTATION } from '@/features/vehicles/vehicleStatus'
import { formatDateTime } from '@/shared/format'
import { Button } from '@/shared/ui/Button'
import { BarChart, DonutChart } from '@/shared/ui/charts'
import { EmptyState } from '@/shared/ui/EmptyState'

import './dashboard.css'

const REFRESH_MS = 30_000

const STATUS_COLORS = {
  moving: 'var(--color-success)',
  stopped: 'var(--palette-red-dark)',
  offline: 'var(--palette-gray)',
} as const

interface KpiProps {
  readonly label: string
  readonly value: number | string
  readonly hint?: string
  readonly accent?: boolean
}

function Kpi({ label, value, hint, accent = false }: KpiProps) {
  return (
    <div className={`kpi${accent ? ' kpi--accent' : ''}`}>
      <dt className="kpi__label">{label}</dt>
      <dd className="kpi__value">{value}</dd>
      {hint && <dd className="kpi__hint">{hint}</dd>}
    </div>
  )
}

export function DashboardPage() {
  const summary = useQuery({ queryKey: fleetKeys.summary, queryFn: fleetApi.summary, refetchInterval: REFRESH_MS })

  return (
    <section aria-labelledby="page-title">
      <header className="page-header">
        <p className="page-eyebrow">Panel de flota</p>
        <h1 id="page-title" className="page-title">
          Resumen
        </h1>
        <p className="page-subtitle" aria-live="polite">
          {summary.data
            ? `Actualizado: ${formatDateTime(summary.data.generatedAt)} (hora Colombia)`
            : 'Estado de la flota en tiempo real.'}
        </p>
      </header>

      {summary.isPending && <p className="ui-page-status" role="status">Cargando indicadores…</p>}

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
            <Kpi label="Vehículos" value={summary.data.totalVehicles} accent />
            <Kpi label={VEHICLE_STATUS_PRESENTATION.moving.label} value={summary.data.byStatus.moving} />
            <Kpi label={VEHICLE_STATUS_PRESENTATION.stopped.label} value={summary.data.byStatus.stopped} />
            <Kpi
              label={VEHICLE_STATUS_PRESENTATION.offline.label}
              value={summary.data.byStatus.offline}
              hint="Sin reportar en más de 30 min"
            />
            <Kpi label="Conductores" value={summary.data.totalDrivers} />
            <Kpi label="Pasajeros" value={summary.data.totalPassengers} />
          </dl>

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
            </article>
          </div>
        </>
      )}
    </section>
  )
}
