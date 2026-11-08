/**
 * Pantalla de inicio de sesión.
 *
 * Flujo: validar en cliente (zod) -> login() del AuthProvider -> redirigir a la
 * página que se intentaba abrir (state.from de RequireAuth) o al panel.
 * Los errores del servidor (401, red...) llegan como ApiError con mensaje en español.
 */
import { type FormEvent, useState } from 'react'
import { type Location, Navigate, useLocation } from 'react-router-dom'

import { ApiError } from '@/shared/api/problem'
import { useAuth } from '@/shared/auth/useAuth'
import { Button } from '@/shared/ui/Button'
import { TextField } from '@/shared/ui/TextField'

import { type LoginFieldErrors, validateLogin } from './loginSchema'
import './login.css'

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
    <section className="login" aria-labelledby="login-title">
      <div className="login__card page-card">
        <header className="page-header">
          <p className="page-eyebrow">Acceso al panel</p>
          <h1 id="login-title" className="page-title">
            Inicia sesión
          </h1>
          <p className="login__subtitle">Usa las credenciales que te entregó el administrador.</p>
        </header>

        {/* noValidate: usamos nuestra validación (mensajes en español y consistentes). */}
        <form className="login__form" onSubmit={handleSubmit} noValidate>
          {formError && (
            <p className="ui-alert" role="alert">
              {formError}
            </p>
          )}
          <TextField
            label="Correo electrónico"
            name="email"
            type="email"
            autoComplete="username"
            error={fieldErrors.email}
            disabled={isSubmitting}
          />
          <TextField
            label="Contraseña"
            name="password"
            type="password"
            autoComplete="current-password"
            error={fieldErrors.password}
            disabled={isSubmitting}
          />
          <Button type="submit" variant="primary" isLoading={isSubmitting}>
            {isSubmitting ? 'Ingresando…' : 'Ingresar'}
          </Button>
        </form>
      </div>
    </section>
  )
}
