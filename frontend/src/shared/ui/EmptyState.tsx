/**
 * Estado vacío: se muestra cuando no hay datos que listar o no hay acceso.
 *
 * <EmptyState title="Sin vehículos" description="..." action={<Button>Recargar</Button>} />
 *
 * Un estado vacío explícito evita la duda "¿está cargando o no hay nada?".
 */
import type { ReactNode } from 'react'

import './styles/components.css'

interface EmptyStateProps {
  readonly title: string
  readonly description?: string
  readonly action?: ReactNode // botón opcional para salir del estado vacío
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="ui-empty">
      <p className="ui-empty__title">{title}</p>
      {description && <p className="ui-empty__description">{description}</p>}
      {action && <div className="ui-empty__action">{action}</div>}
    </div>
  )
}
