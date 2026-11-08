/**
 * Enlace de navegación con apariencia de botón: <ButtonLink to="/login" variant="primary">Ingresar</ButtonLink>
 *
 * ¿Por qué no <Button onClick={navigate}>? Semántica: si lleva a otra página es un
 * ENLACE (<a>): se puede abrir en pestaña nueva, copiar, y el lector de pantalla
 * lo anuncia como "enlace". Reutiliza las clases de Button (mismo aspecto, sin duplicar CSS).
 */
import { Link, type LinkProps } from 'react-router-dom'

import type { ButtonSize, ButtonVariant } from './Button'
import { cx } from './cx'
import './styles/components.css'

interface ButtonLinkProps extends LinkProps {
  readonly variant?: ButtonVariant
  readonly size?: ButtonSize
}

export function ButtonLink({ variant = 'secondary', size = 'md', className, ...linkProps }: ButtonLinkProps) {
  return (
    <Link
      className={cx(
        'ui-button',
        variant !== 'secondary' && `ui-button--${variant}`,
        size === 'sm' && 'ui-button--sm',
        className,
      )}
      {...linkProps}
    />
  )
}
