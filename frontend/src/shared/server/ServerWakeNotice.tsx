/**
 * Aviso de arranque en frío (DEP-04): nunca una pantalla en blanco ni un error genérico.
 *
 * - waking: role="status" (el lector de pantalla lo anuncia sin interrumpir).
 * - down:   role="alert" + botón Reintentar.
 * - resto:  no muestra nada.
 */
import { Button } from '@/shared/ui/Button'

import { backendWakeup, useBackendStatus } from './backendStatus'

export function ServerWakeNotice() {
  const status = useBackendStatus()

  if (status === 'waking') {
    return (
      <p className="ui-alert ui-alert--info" role="status" aria-live="polite">
        <span className="ui-button__spinner" aria-hidden="true" /> Iniciando el servidor, puede tardar hasta un
        minuto. No cierres esta página.
      </p>
    )
  }

  if (status === 'down') {
    return (
      <div className="ui-alert" role="alert">
        <p>No pudimos conectar con el servidor.</p>
        <Button size="sm" onClick={() => void backendWakeup.retry().catch(() => undefined)}>
          Reintentar
        </Button>
      </div>
    )
  }

  return null
}
