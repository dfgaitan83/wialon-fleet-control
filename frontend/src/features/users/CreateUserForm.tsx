/**
 * Alta de usuario (RF-06): correo, nombre y rol. La contraseña la genera el backend.
 * Validación declarativa con zod en el cliente; el backend vuelve a validar (422/409).
 */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useId, useState } from 'react'
import { z } from 'zod'

import { ApiError } from '@/shared/api/problem'
import { Button } from '@/shared/ui/Button'
import { TextField } from '@/shared/ui/TextField'

import { type ManagedUser, type Role, usersApi, usersKeys } from './usersApi'

const schema = z.object({
  email: z.string().trim().min(1, 'Ingresa el correo').pipe(z.email('El correo no es válido')),
  fullName: z.string().trim().min(1, 'Ingresa el nombre').max(120, 'Máximo 120 caracteres'),
  role: z.string().min(1, 'Elige un rol'),
})
type FieldErrors = Partial<Record<keyof z.infer<typeof schema>, string>>

interface CreateUserFormProps {
  readonly roles: readonly Role[]
  readonly onCreated: (user: ManagedUser, temporaryPassword: string) => void
}

export function CreateUserForm({ roles, onCreated }: CreateUserFormProps) {
  const queryClient = useQueryClient()
  const roleId = useId()
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: usersApi.create,
    onSuccess: ({ user, temporaryPassword }) => {
      void queryClient.invalidateQueries({ queryKey: usersKeys.all }) // la lista se recarga
      onCreated(user, temporaryPassword)
    },
    onError: (error: unknown) => {
      if (error instanceof ApiError && error.fieldErrors.email) setErrors({ email: error.fieldErrors.email[0] })
      else setFormError(error instanceof ApiError ? error.message : 'No se pudo crear el usuario.')
    },
  })

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const formElement = event.currentTarget
    const form = new FormData(formElement)
    const result = schema.safeParse({
      email: String(form.get('email') ?? ''),
      fullName: String(form.get('fullName') ?? ''),
      role: String(form.get('role') ?? ''),
    })
    setFormError(null)
    if (!result.success) {
      const next: FieldErrors = {}
      for (const issue of result.error.issues) next[issue.path[0] as keyof FieldErrors] ??= issue.message
      setErrors(next)
      return
    }
    setErrors({})
    mutation.mutate(result.data, { onSuccess: () => formElement.reset() })
  }

  return (
    <form className="users-create" onSubmit={handleSubmit} noValidate aria-labelledby="create-user-title">
      <h2 id="create-user-title" className="users-section-title">
        Nuevo usuario
      </h2>
      {formError && (
        <p className="ui-alert" role="alert">
          {formError}
        </p>
      )}
      <div className="users-create__fields">
        <TextField label="Correo electrónico" name="email" type="email" autoComplete="off" error={errors.email} />
        <TextField label="Nombre completo" name="fullName" autoComplete="off" error={errors.fullName} />
        <div className="ui-field">
          <label htmlFor={roleId} className="ui-field__label">
            Rol
          </label>
          <select id={roleId} name="role" className="ui-field__input" defaultValue="viewer">
            {roles.map((role) => (
              <option key={role.name} value={role.name}>
                {role.label}
              </option>
            ))}
          </select>
        </div>
      </div>
      <Button type="submit" variant="primary" isLoading={mutation.isPending}>
        {mutation.isPending ? 'Creando…' : 'Crear usuario'}
      </Button>
    </form>
  )
}
