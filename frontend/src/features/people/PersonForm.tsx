/**
 * Alta / edición de conductor o pasajero (RF-18, RF-28: validación en cliente Y servidor).
 * Errores del backend por campo (422) y conflictos (409: código o teléfono repetido) se
 * muestran junto al campo o arriba del formulario.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { z } from 'zod'

import { ApiError } from '@/shared/api/problem'
import { Button } from '@/shared/ui/Button'
import { TextField } from '@/shared/ui/TextField'

import { CustomFieldsEditor, type FieldRow } from './CustomFieldsEditor'
import { KIND_TEXT, peopleApi, peopleKeys, type Person, type PersonKind } from './peopleApi'

const schema = z.object({
  name: z.string().trim().min(1, 'El nombre es obligatorio').max(50, 'Máximo 50 caracteres'),
  code: z.string().trim().max(30, 'Máximo 30 caracteres'),
  description: z.string().trim().max(200, 'Máximo 200 caracteres'),
  phone: z
    .string()
    .trim()
    .refine((v) => v === '' || /^\+?[0-9][0-9 ()-]{5,19}$/.test(v), 'Teléfono no válido (ej. +57 300 000 0000)'),
})
type FieldErrors = Partial<Record<'name' | 'code' | 'description' | 'phone' | 'custom_fields', string>>

interface PersonFormProps {
  readonly kind: PersonKind
  readonly person: Person | null // null = crear
  readonly onDone: (message: string) => void
  readonly onCancel: () => void
}

function rowsToFields(rows: readonly FieldRow[]): Record<string, string> | string {
  const fields: Record<string, string> = {}
  for (const row of rows) {
    const key = row.key.trim()
    if (!key && !row.value.trim()) continue // fila vacía: se ignora
    if (!key) return 'Cada campo necesita un nombre.'
    if (key in fields) return `El campo “${key}” está repetido.`
    fields[key] = row.value.trim()
  }
  return fields
}

export function PersonForm({ kind, person, onDone, onCancel }: PersonFormProps) {
  const text = KIND_TEXT[kind]
  const queryClient = useQueryClient()
  const [rows, setRows] = useState<FieldRow[]>(
    Object.entries(person?.customFields ?? {}).map(([key, value]) => ({ key, value })),
  )
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (input: Parameters<typeof peopleApi.create>[1]) =>
      person ? peopleApi.update(kind, person, input) : peopleApi.create(kind, input),
    onSuccess: (saved) => {
      void queryClient.invalidateQueries({ queryKey: peopleKeys.all(kind) })
      void queryClient.invalidateQueries({ queryKey: ['fleet'] }) // el vehículo muestra a la persona
      onDone(`${saved.name} ${person ? 'actualizado' : 'creado'} en Wialon.`)
    },
    onError: (error: unknown) => {
      if (error instanceof ApiError && Object.keys(error.fieldErrors).length > 0) {
        setErrors(Object.fromEntries(Object.entries(error.fieldErrors).map(([k, v]) => [k, v[0]])) as FieldErrors)
      }
      setFormError(error instanceof ApiError ? error.message : 'No se pudo guardar.')
    },
  })

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const result = schema.safeParse(Object.fromEntries(['name', 'code', 'description', 'phone'].map((k) => [k, String(form.get(k) ?? '')])))
    const fields = rowsToFields(rows)
    const next: FieldErrors = {}
    if (!result.success) for (const issue of result.error.issues) next[issue.path[0] as keyof FieldErrors] ??= issue.message
    if (typeof fields === 'string') next.custom_fields = fields
    setErrors(next)
    setFormError(null)
    if (!result.success || typeof fields === 'string') return
    mutation.mutate({ ...result.data, customFields: fields })
  }

  const busy = mutation.isPending
  return (
    <form className="person-form" onSubmit={handleSubmit} noValidate aria-labelledby="person-form-title">
      <h2 id="person-form-title" className="people-section-title">
        {person ? `Editar ${text.singular}: ${person.name}` : `Nuevo ${text.singular}`}
      </h2>
      {formError && (
        <p className="ui-alert" role="alert">
          {formError}
        </p>
      )}
      <div className="person-form__grid">
        <TextField label="Nombre completo" name="name" defaultValue={person?.name} error={errors.name} disabled={busy} required />
        <TextField label="Código" name="code" defaultValue={person?.code} error={errors.code} hint="Único (ej. C-014)" disabled={busy} />
        {text.hasPhone && (
          <TextField label="Teléfono" name="phone" type="tel" inputMode="tel" defaultValue={person?.phone} error={errors.phone} disabled={busy} />
        )}
        <TextField label="Descripción" name="description" defaultValue={person?.description} error={errors.description} disabled={busy} />
      </div>
      <CustomFieldsEditor rows={rows} onChange={setRows} error={errors.custom_fields} disabled={busy} />
      <div className="person-form__actions">
        <Button type="submit" variant="primary" isLoading={busy}>
          {busy ? 'Guardando en Wialon…' : person ? 'Guardar cambios' : `Crear ${text.singular}`}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={busy}>
          Cancelar
        </Button>
      </div>
    </form>
  )
}
