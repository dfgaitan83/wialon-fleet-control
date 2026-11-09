/**
 * Editor de campos personalizados (RF-27): crear, editar y eliminar pares nombre/valor.
 * Controlado: recibe y devuelve la lista completa (el backend reemplaza el conjunto
 * entero, así un campo borrado aquí se borra en Wialon; los no tocados se conservan).
 */
import { useId } from 'react'

import { Button } from '@/shared/ui/Button'

export interface FieldRow {
  readonly key: string
  readonly value: string
}

interface CustomFieldsEditorProps {
  readonly rows: readonly FieldRow[]
  readonly onChange: (rows: FieldRow[]) => void
  readonly error?: string
  readonly disabled?: boolean
}

export function CustomFieldsEditor({ rows, onChange, error, disabled = false }: CustomFieldsEditorProps) {
  const id = useId()
  const update = (index: number, patch: Partial<FieldRow>) =>
    onChange(rows.map((row, i) => (i === index ? { ...row, ...patch } : row))) // copia nueva (inmutable)

  return (
    <fieldset className="fields-editor" aria-describedby={error ? `${id}-error` : undefined}>
      <legend className="ui-field__label">Campos personalizados</legend>
      {rows.length === 0 && <p className="fields-editor__empty">Sin campos. Añade, por ejemplo, “Ruta” o “Licencia”.</p>}
      {rows.map((row, index) => (
        <div key={index} className="fields-editor__row">
          <label className="ui-visually-hidden" htmlFor={`${id}-k${index}`}>
            Nombre del campo {index + 1}
          </label>
          <input
            id={`${id}-k${index}`}
            className="ui-field__input"
            placeholder="Nombre (ej. Ruta)"
            value={row.key}
            disabled={disabled}
            onChange={(e) => update(index, { key: e.target.value })}
          />
          <label className="ui-visually-hidden" htmlFor={`${id}-v${index}`}>
            Valor del campo {index + 1}
          </label>
          <input
            id={`${id}-v${index}`}
            className="ui-field__input"
            placeholder="Valor"
            value={row.value}
            disabled={disabled}
            onChange={(e) => update(index, { value: e.target.value })}
          />
          <Button
            size="sm"
            variant="ghost"
            aria-label={`Eliminar el campo ${row.key || index + 1}`}
            disabled={disabled}
            onClick={() => onChange(rows.filter((_, i) => i !== index))}
          >
            Quitar
          </Button>
        </div>
      ))}
      <Button size="sm" disabled={disabled} onClick={() => onChange([...rows, { key: '', value: '' }])}>
        + Añadir campo
      </Button>
      {error && (
        <p id={`${id}-error`} role="alert" className="ui-field__error">
          {error}
        </p>
      )}
    </fieldset>
  )
}
