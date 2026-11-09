/**
 * Gráficos SVG livianos del sistema de diseño (RF-23): dona y barras horizontales.
 *
 * ¿Por qué SVG propio y no una librería? ~2 KB frente a ~100 KB (cuenta para el
 * Lighthouse de UX-07), colores SIEMPRE de la paleta (tokens CSS) y accesibilidad
 * completa: role="img" con descripción + tabla equivalente oculta para lectores de pantalla.
 */
import './styles/charts.css'

export interface ChartSegment {
  readonly label: string
  readonly value: number
  readonly color: string // variable CSS de la paleta, p. ej. "var(--color-success)"
}

interface ChartProps {
  readonly title: string
  readonly segments: readonly ChartSegment[]
}

const RADIUS = 42
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

function describe(segments: readonly ChartSegment[], total: number): string {
  return segments.map((s) => `${s.label}: ${s.value} de ${total}`).join('; ')
}

function DataTable({ title, segments }: ChartProps) {
  return (
    <table className="ui-visually-hidden">
      <caption>{title}</caption>
      <tbody>
        {segments.map((s) => (
          <tr key={s.label}>
            <th scope="row">{s.label}</th>
            <td>{s.value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Legend({ segments, total }: { readonly segments: readonly ChartSegment[]; readonly total: number }) {
  return (
    <ul className="ui-chart__legend" aria-hidden="true">
      {segments.map((s) => (
        <li key={s.label}>
          <span className="ui-chart__swatch" style={{ background: s.color }} />
          <span className="ui-chart__legend-label">{s.label}</span>
          <span className="ui-chart__legend-value">
            {s.value}
            <span className="ui-chart__legend-pct"> · {total ? Math.round((s.value / total) * 100) : 0}%</span>
          </span>
        </li>
      ))}
    </ul>
  )
}

/** Dona: proporción de cada parte sobre el total (p. ej. vehículos por estado). */
/** Longitud y desplazamiento de cada arco, calculados SIN mutar (cada uno empieza donde acaba el anterior). */
function arcs(segments: readonly ChartSegment[], total: number) {
  const lengths = segments.map((s) => (total ? (s.value / total) * CIRCUMFERENCE : 0))
  return segments.map((segment, index) => ({
    segment,
    length: lengths[index],
    offset: lengths.slice(0, index).reduce((sum, length) => sum + length, 0),
  }))
}

export function DonutChart({ title, segments }: ChartProps) {
  const total = segments.reduce((sum, s) => sum + s.value, 0)
  return (
    <figure className="ui-chart">
      <svg viewBox="0 0 100 100" className="ui-chart__donut" role="img" aria-label={`${title}. ${describe(segments, total)}`}>
        <circle cx="50" cy="50" r={RADIUS} className="ui-chart__track" />
        {arcs(segments, total).map(({ segment, length, offset }) => (
          <circle
            key={segment.label}
            cx="50"
            cy="50"
            r={RADIUS}
            className="ui-chart__arc"
            stroke={segment.color}
            strokeDasharray={`${length} ${CIRCUMFERENCE - length}`}
            strokeDashoffset={-offset}
          />
        ))}
        <text x="50" y="48" className="ui-chart__total">
          {total}
        </text>
        <text x="50" y="62" className="ui-chart__total-label">
          total
        </text>
      </svg>
      <Legend segments={segments} total={total} />
      <DataTable title={title} segments={segments} />
    </figure>
  )
}

/** Barras horizontales: comparar magnitudes (p. ej. con / sin conductor). */
export function BarChart({ title, segments }: ChartProps) {
  const total = segments.reduce((sum, s) => sum + s.value, 0)
  const max = Math.max(1, ...segments.map((s) => s.value))
  return (
    <figure className="ui-chart">
      <div role="img" aria-label={`${title}. ${describe(segments, total)}`} className="ui-chart__bars">
        {segments.map((s) => (
          <div key={s.label} className="ui-chart__bar-row" aria-hidden="true">
            <span className="ui-chart__bar-label">{s.label}</span>
            <span className="ui-chart__bar-track">
              <span className="ui-chart__bar" style={{ inlineSize: `${(s.value / max) * 100}%`, background: s.color }} />
            </span>
            <span className="ui-chart__bar-value">{s.value}</span>
          </div>
        ))}
      </div>
      <DataTable title={title} segments={segments} />
    </figure>
  )
}
