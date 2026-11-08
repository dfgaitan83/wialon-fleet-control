/**
 * Botón base de la app.
 *
 * <Button variant="primary" isLoading={saving} onClick={save}>Guardar</Button>
 *
 * Decisiones:
 * - type="button" por defecto: un <button> dentro de un <form> es "submit" por
 *   defecto en HTML y enviaría el formulario sin querer. Para enviar: type="submit".
 * - isLoading desactiva el botón y anuncia "ocupado" (aria-busy) -> evita doble clic
 *   que crearía dos peticiones (ej. dos ediciones del mismo conductor).
 * - Acepta todas las props nativas de <button> (aria-*, onClick, ref...).
 */
import type { ComponentPropsWithRef, ReactNode } from 'react'

import { cx } from './cx'
import './styles/components.css'

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost'
export type ButtonSize = 'sm' | 'md'

interface ButtonProps extends ComponentPropsWithRef<'button'> {
  readonly variant?: ButtonVariant
  readonly size?: ButtonSize
  readonly isLoading?: boolean
  readonly leadingIcon?: ReactNode // icono opcional a la izquierda del texto
}

export function Button({
  variant = 'secondary',
  size = 'md',
  isLoading = false,
  leadingIcon,
  type = 'button',
  disabled,
  className,
  children,
  ...rest // resto de props nativas (onClick, aria-label, ref...) pasan tal cual
}: ButtonProps) {
  return (
    <button
      type={type}
      // Desactivado si lo piden o mientras carga.
      disabled={disabled || isLoading}
      aria-busy={isLoading || undefined} // undefined = no renderizar el atributo
      className={cx(
        'ui-button',
        variant !== 'secondary' && `ui-button--${variant}`, // secondary es el estilo base
        size === 'sm' && 'ui-button--sm',
        className,
      )}
      {...rest}
    >
      {/* Durante la carga el spinner sustituye al icono; aria-hidden: es decorativo. */}
      {isLoading ? <span className="ui-button__spinner" aria-hidden="true" /> : leadingIcon}
      {children}
    </button>
  )
}
