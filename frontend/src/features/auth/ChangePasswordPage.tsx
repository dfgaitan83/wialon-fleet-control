/**
 * Cambio de contraseña (RF-06). Obligatorio cuando el Admin creó o restableció la
 * cuenta (contraseña temporal): RequireAuth redirige aquí y no deja salir hasta
 * cambiarla. También sirve para un cambio voluntario.
 *
 * Errores del servidor por campo (422: contraseña actual incorrecta, política) se
 * muestran junto al campo correspondiente.
 */
import { type FormEvent, useState } from 'react'
import { Navigate } from 'react-router-dom'

import { ApiError } from '@/shared/api/problem'
import { useAuth } from '@/shared/auth/useAuth'
import { Button } from '@/shared/ui/Button'
import { PasswordField } from '@/shared/ui/PasswordField'

import { type ChangePasswordErrors, PASSWORD_MIN_LENGTH, validateChangePassword } from './changePasswordSchema'
import { AuthShell } from './AuthShell'

const APP_HOME = '/app'
const UNEXPECTED_ERROR = 'No se pudo cambiar la contraseña. Inténtalo de nuevo.'
// Campos del backend (snake_case) -> campos del formulario.
const SERVER_FIELDS: Record<string, keyof ChangePasswordErrors> = {
  current_password: 'currentPassword',
  new_password: 'newPassword',
}

function serverFieldErrors(error: ApiError): ChangePasswordErrors {
  const mapped: ChangePasswordErrors = {}
  for (const [field, messages] of Object.entries(error.fieldErrors)) {
    const target = SERVER_FIELDS[field]
    if (target && messages[0]) mapped[target] = messages[0]
  }
  return mapped
}

export function ChangePasswordPage() {
  const { user, changePassword } = useAuth()
  const [fieldErrors, setFieldErrors] = useState<ChangePasswordErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [done, setDone] = useState(false)

  if (done) return <Navigate to={APP_HOME} replace />
  if (user === null) return null // RequireAuth garantiza sesión; defensa por si acaso

  const isMandatory = user.mustChangePassword

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const result = validateChangePassword(
      {
        currentPassword: String(form.get('currentPassword') ?? ''),
        newPassword: String(form.get('newPassword') ?? ''),
        confirmPassword: String(form.get('confirmPassword') ?? ''),
      },
      user.email,
    )
    if ('errors' in result) {
      setFieldErrors(result.errors)
      return
    }
    setFieldErrors({})
    setFormError(null)
    setIsSubmitting(true)
    try {
      await changePassword(result.data)
      setDone(true)
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        const byField = serverFieldErrors(error)
        setFieldErrors(byField)
        if (Object.keys(byField).length === 0) setFormError(error.message)
      } else {
        setFormError(UNEXPECTED_ERROR)
      }
      setIsSubmitting(false)
    }
  }

  return (
    <AuthShell
      eyebrow="Seguridad de la cuenta"
      title={isMandatory ? 'Crea tu contraseña' : 'Cambiar contraseña'}
      titleId="change-password-title"
      subtitle={
        isMandatory
          ? 'Estás usando una contraseña temporal. Para continuar, elige una nueva que solo tú conozcas.'
          : 'Al cambiarla se cerrarán tus otras sesiones abiertas.'
      }
    >
      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        {formError && (
          <p className="ui-alert" role="alert">
            {formError}
          </p>
        )}
        <PasswordField
          label={isMandatory ? 'Contraseña temporal' : 'Contraseña actual'}
          name="currentPassword"
          autoComplete="current-password"
          error={fieldErrors.currentPassword}
          disabled={isSubmitting}
        />
        <PasswordField
          label="Nueva contraseña"
          name="newPassword"
          autoComplete="new-password"
          hint={`Mínimo ${PASSWORD_MIN_LENGTH} caracteres, con letras y números.`}
          error={fieldErrors.newPassword}
          disabled={isSubmitting}
        />
        <PasswordField
          label="Repite la nueva contraseña"
          name="confirmPassword"
          autoComplete="new-password"
          error={fieldErrors.confirmPassword}
          disabled={isSubmitting}
        />
        <Button type="submit" variant="primary" isLoading={isSubmitting}>
          {isSubmitting ? 'Guardando…' : 'Guardar contraseña'}
        </Button>
      </form>
    </AuthShell>
  )
}
