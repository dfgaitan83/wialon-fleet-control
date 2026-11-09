/**
 * Campo de contraseña con botón "Mostrar / Ocultar" (UX: password-toggle).
 *
 * Mismo contrato y estilos que TextField (etiqueta, error y ayuda accesibles). El
 * botón usa aria-pressed (el lector anuncia "presionado") y aria-controls (indica
 * qué campo cambia). Nunca guarda ni registra el valor: solo cambia el type.
 */
import { type ComponentPropsWithRef, useId, useState } from 'react'

import { cx } from './cx'
import './styles/components.css'

interface PasswordFieldProps extends Omit<ComponentPropsWithRef<'input'>, 'id' | 'type'> {
  readonly label: string
  readonly error?: string
  readonly hint?: string
}

function EyeIcon({ open }: { readonly open: boolean }) {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
      <circle cx="12" cy="12" r="3" />
      {!open && <path d="M4 4l16 16" />}
    </svg>
  )
}

export function PasswordField({ label, error, hint, className, ...inputProps }: PasswordFieldProps) {
  const id = useId()
  const [visible, setVisible] = useState(false)
  const errorId = `${id}-error`
  const hintId = `${id}-hint`
  const describedBy = cx(error && errorId, hint && hintId) || undefined

  return (
    <div className={cx('ui-field', className)}>
      <label htmlFor={id} className="ui-field__label">
        {label}
      </label>
      <div className="ui-field__control">
        <input
          id={id}
          type={visible ? 'text' : 'password'}
          className="ui-field__input ui-field__input--with-action"
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          {...inputProps}
        />
        <button
          type="button"
          className="ui-field__action"
          aria-pressed={visible}
          aria-controls={id}
          aria-label={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}
          title={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}
          onClick={() => setVisible((v) => !v)}
          disabled={inputProps.disabled}
        >
          <EyeIcon open={visible} />
        </button>
      </div>
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
