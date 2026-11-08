/**
 * Pantalla de error inesperado (errorElement del router).
 * Si un componente lanza una excepción al renderizar, React Router muestra esto
 * en lugar de dejar la pantalla en blanco. NO muestra el detalle técnico al
 * usuario (podría exponer información interna).
 */
import { EmptyState } from '@/shared/ui/EmptyState'
import { ButtonLink } from '@/shared/ui/ButtonLink'

export function RouteErrorPage() {
  return (
    <main className="ui-page-status">
      <EmptyState
        title="Algo salió mal"
        description="Ocurrió un error inesperado al mostrar esta pantalla. Intenta volver al inicio."
        action={
          <ButtonLink to="/" variant="primary">
            Volver al inicio
          </ButtonLink>
        }
      />
    </main>
  )
}
