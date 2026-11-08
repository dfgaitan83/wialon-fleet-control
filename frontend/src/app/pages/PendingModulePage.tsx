/**
 * Página temporal para módulos que aún no se construyen.
 * UNA sola página parametrizada en lugar de siete archivos casi iguales (DRY).
 * Cuando el módulo exista, se asigna `page` en navigation.ts y esta deja de usarse.
 */
import { EmptyState } from '@/shared/ui/EmptyState' // EmptyState ya carga components.css (page-*)

interface PendingModulePageProps {
  readonly title: string
  readonly milestone: string // meta del plan (ej. "M7")
}

export function PendingModulePage({ title, milestone }: PendingModulePageProps) {
  return (
    <section aria-labelledby="page-title">
      <header className="page-header">
        <p className="page-eyebrow">Panel de flota</p>
        <h1 id="page-title" className="page-title">
          {title}
        </h1>
      </header>
      <div className="page-card">
        <EmptyState
          title="Módulo en construcción"
          description={`Este módulo se implementa en la meta ${milestone} del plan. La navegación, los permisos y el layout ya están listos.`}
        />
      </div>
    </section>
  )
}
