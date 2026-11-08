/**
 * Une clases CSS ignorando valores vacíos:
 *   cx('ui-button', isPrimary && 'ui-button--primary', className)
 * Evita dependencias externas (clsx) para algo de 3 líneas.
 */
export function cx(...classes: ReadonlyArray<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ')
}
