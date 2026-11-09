/**
 * Pantalla de inicio de sesión.
 *
 * Flujo: validar en cliente (zod) -> login() del AuthProvider -> redirigir a la
 * página que se intentaba abrir (state.from de RequireAuth) o al panel.
 * Los errores del servidor (401, red...) llegan como ApiError con mensaje en español.
 */
import { type FormEvent, useEffect, useState } from 'react'
import { type Location, Navigate, useLocation } from 'react-router-dom'

import { ApiError } from '@/shared/api/problem'
import { useAuth } from '@/shared/auth/useAuth'
import { backendWakeup } from '@/shared/server/backendStatus'
import { ServerWakeNotice } from '@/shared/server/ServerWakeNotice'
import { Button } from '@/shared/ui/Button'
import { PasswordField } from '@/shared/ui/PasswordField'
import { TextField } from '@/shared/ui/TextField'

import { AuthShell } from './AuthShell'
import { type LoginFieldErrors, validateLogin } from './loginSchema'

const DEFAULT_REDIRECT = '/app'
const UNEXPECTED_ERROR = 'No se pudo iniciar sesión. Inténtalo de nuevo.'

/** A dónde volver tras el login: la ruta protegida original o el panel. */
function redirectTarget(state: unknown): string {
  const from = (state as { from?: Location } | null)?.from
  return from ? `${from.pathname}${from.search}` : DEFAULT_REDIRECT
}

export function LoginPage() {
  const { status, login } = useAuth()
  const location = useLocation()
  const [fieldErrors, setFieldErrors] = useState<LoginFieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null) // error general (ej. credenciales)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // DEP-04: despierta el backend en cuanto se abre el login. Mientras el usuario
  // escribe, Render ya va arrancando; al enviar, normalmente ya está listo.
  useEffect(() => {
    void backendWakeup.ensureReady().catch(() => undefined) // el aviso ya muestra el fallo
  }, [])

  // ÚNICA fuente de redirección: en cuanto hay sesión (recién iniciada o previa),
  // se va a la página que se intentaba abrir o al panel. Tener un navigate() extra
  // tras el login creaba una carrera con este <Navigate> (detectada por los tests).
  if (status === 'authenticated') return <Navigate to={redirectTarget(location.state)} replace />

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault() // evita la recarga de página del envío HTML clásico
    const form = new FormData(event.currentTarget) // lee los campos por su "name"
    const result = validateLogin({
      email: String(form.get('email') ?? ''),
      password: String(form.get('password') ?? ''),
    })
    if ('errors' in result) {
      setFieldErrors(result.errors)
      return // no se llama al servidor con datos inválidos
    }

    setFieldErrors({})
    setFormError(null)
    setIsSubmitting(true)
    try {
      await login(result.data) // al resolverse, status = authenticated y el <Navigate> de arriba redirige
    } catch (error: unknown) {
      setFormError(error instanceof ApiError ? error.message : UNEXPECTED_ERROR)
      setIsSubmitting(false) // solo en error: si hubo éxito el componente se desmonta al redirigir
    }
  }

  return (
    <AuthShell
      eyebrow="Acceso al panel"
      title="Inicia sesión"
      titleId="login-title"
      subtitle="Usa las credenciales que te entregó el administrador."
    >
      {/* noValidate: usamos nuestra validación (mensajes en español y consistentes). */}
      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        <ServerWakeNotice />
        {formError && (
          <p className="ui-alert" role="alert">
            {formError}
          </p>
        )}
        <TextField
          label="Correo electrónico"
          name="email"
          type="email"
          inputMode="email"
          autoComplete="username"
          placeholder="nombre@empresa.com"
          error={fieldErrors.email}
          disabled={isSubmitting}
        />
        <PasswordField
          label="Contraseña"
          name="password"
          autoComplete="current-password"
          error={fieldErrors.password}
          disabled={isSubmitting}
        />
        <Button type="submit" variant="primary" isLoading={isSubmitting}>
          {isSubmitting ? 'Ingresando…' : 'Ingresar'}
        </Button>
        <p className="auth-help">¿Olvidaste tu contraseña? Pide al administrador que la restablezca.</p>
      </form>
    </AuthShell>
  )
}
