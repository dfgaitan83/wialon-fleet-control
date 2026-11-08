/** Página 404: cualquier URL que no coincide con una ruta. */
import { ButtonLink } from '@/shared/ui/ButtonLink'
import { EmptyState } from '@/shared/ui/EmptyState'

export function NotFoundPage() {
  return (
    <EmptyState
      title="Página no encontrada"
      description="La dirección que buscas no existe o fue movida."
      action={
        <ButtonLink to="/" variant="primary">
          Volver al inicio
        </ButtonLink>
      }
    />
  )
}
