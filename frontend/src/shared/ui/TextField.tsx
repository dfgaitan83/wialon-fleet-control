/**
 * Campo de texto con etiqueta y mensaje de error accesibles.
 *
 * <TextField label="Correo" name="email" type="email" error={errors.email} />
 *
 * Accesibilidad:
 * - <label htmlFor> enlazado al input: clic en la etiqueta enfoca el campo y el
 *   lector de pantalla lee el nombre.
 * - aria-invalid + aria-describedby: el lector anuncia "inválido" y lee el error.
 * - role="alert" en el error: se anuncia en cuanto aparece.
 */
import { type ComponentPropsWithRef, useId } from 'react'

import { cx } from './cx'
import './styles/components.css'

interface TextFieldProps extends Omit<ComponentPropsWithRef<'input'>, 'id'> {
  readonly label: string
  readonly error?: string // mensaje de validación (si existe, el campo se marca inválido)
  readonly hint?: string // ayuda opcional bajo el campo
}

export function TextField({ label, error, hint, className, ...inputProps }: TextFieldProps) {
  const id = useId() // id único y estable (también en SSR): enlaza label, input y mensajes
  const errorId = `${id}-error`
  const hintId = `${id}-hint`
  const describedBy = cx(error && errorId, hint && hintId) || undefined

  return (
    <div className={cx('ui-field', className)}>
      <label htmlFor={id} className="ui-field__label">
        {label}
      </label>
      <input
        id={id}
        className="ui-field__input"
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        {...inputProps}
      />
      {hint && !error && (
        <p id={hintId} className="ui-field__hint">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" className="ui-field__error">
          {error}
        </p>
      )}
    </div>
  )
}
