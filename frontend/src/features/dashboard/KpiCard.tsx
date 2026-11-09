/**
 * Tarjeta de indicador: ícono con color semántico, número que cuenta desde 0 y,
 * opcionalmente, una barra con la proporción sobre el total de la flota.
 * `index` escalona la entrada (40 ms por tarjeta) mediante una variable CSS.
 */
import type { CSSProperties, ReactNode } from 'react'

import { useCountUp } from '@/shared/hooks/useCountUp'

export type KpiTone = 'brand' | 'moving' | 'stopped' | 'offline' | 'neutral'

interface KpiCardProps {
  readonly label: string
  readonly value: number
  readonly icon: ReactNode
  readonly tone: KpiTone
  readonly index: number
  readonly share?: { readonly part: number; readonly total: number } // barra de proporción
  readonly hint?: string
}

const percent = new Intl.NumberFormat('es-CO', { style: 'percent', maximumFractionDigits: 0 })

export function KpiCard({ label, value, icon, tone, index, share, hint }: KpiCardProps) {
  const shown = useCountUp(value)
  const ratio = share && share.total > 0 ? share.part / share.total : 0
  const style = { '--i': index, '--ratio': ratio } as CSSProperties

  return (
    <div className={`kpi kpi--${tone}`} style={style}>
      <dt className="kpi__label">
        <span className="kpi__icon">{icon}</span>
        {label}
      </dt>
      <dd className="kpi__value" aria-label={String(value)}>
        {shown}
      </dd>
      {share && (
        <dd className="kpi__share">
          <span className="kpi__share-track" aria-hidden="true">
            <span className="kpi__share-bar" />
          </span>
          <span className="kpi__share-text">{percent.format(ratio)} de la flota</span>
        </dd>
      )}
      {hint && <dd className="kpi__hint">{hint}</dd>}
    </div>
  )
}
