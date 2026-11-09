/**
 * Muestra UNA vez la contraseña temporal generada por el backend (crear / restablecer).
 * No se guarda en ningún lado: al cerrar el aviso desaparece y no se puede recuperar.
 */
import { useState } from 'react'

import { Button } from '@/shared/ui/Button'

interface TemporaryPasswordNoticeProps {
  readonly email: string
  readonly password: string
  readonly onClose: () => void
}

export function TemporaryPasswordNotice({ email, password, onClose }: TemporaryPasswordNoticeProps) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(password)
      setCopied(true)
    } catch {
      setCopied(false) // sin permiso de portapapeles: el usuario puede seleccionarla a mano
    }
  }

  return (
    <div className="users-temp" role="status" aria-live="polite">
      <p className="users-temp__title">Contraseña temporal de {email}</p>
      <code className="users-temp__password">{password}</code>
      <p className="users-temp__hint">
        Entrégala por un canal seguro. Solo se muestra ahora: el usuario deberá cambiarla en su primer ingreso.
      </p>
      <div className="users-temp__actions">
        <Button size="sm" variant="primary" onClick={() => void copy()}>
          {copied ? 'Copiada' : 'Copiar'}
        </Button>
        <Button size="sm" variant="ghost" onClick={onClose}>
          Cerrar
        </Button>
      </div>
    </div>
  )
}
