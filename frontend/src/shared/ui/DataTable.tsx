/**
 * Tabla de datos genérica y tipada.
 *
 * const columns: DataTableColumn<Vehicle>[] = [
 *   { id: 'name', header: 'Vehículo', cell: (v) => v.name },
 *   { id: 'speed', header: 'Velocidad', cell: (v) => `${v.speedKmh} km/h`, align: 'end', numeric: true },
 * ]
 * <DataTable caption="Vehículos" columns={columns} rows={vehicles} getRowId={(v) => v.id} />
 *
 * Decisiones:
 * - Genérica <T>: TypeScript verifica que cada "cell" use campos que existen en T.
 * - La tabla NO pide datos ni ordena/filtra: solo pinta. La lógica vive en la feature
 *   (componente "presentacional" puro -> fácil de probar y reutilizar).
 * - Tres estados explícitos: cargando (filas esqueleto), vacío (EmptyState) y con datos.
 * - <table> semántica con <caption> y scope="col": navegable con lector de pantalla.
 */
import type { ReactNode } from 'react'

import { cx } from './cx'
import { EmptyState } from './EmptyState'
import './styles/components.css'

export type ColumnAlign = 'start' | 'center' | 'end'

export interface DataTableColumn<T> {
  readonly id: string // identificador único de la columna (se usa como key de React)
  readonly header: ReactNode // contenido de la cabecera
  readonly cell: (row: T) => ReactNode // cómo pintar la celda de esta columna para una fila
  readonly align?: ColumnAlign // números a la derecha ("end") para comparar magnitudes
  readonly numeric?: boolean // fuente monoespaciada con cifras tabulares
}

interface DataTableProps<T> {
  readonly caption: string // título accesible (visualmente oculto)
  readonly columns: readonly DataTableColumn<T>[]
  readonly rows: readonly T[]
  readonly getRowId: (row: T) => string // key estable: NUNCA el índice (rompe al reordenar)
  readonly isLoading?: boolean
  readonly skeletonRows?: number // cuántas filas esqueleto mostrar mientras carga
  readonly emptyState?: ReactNode // qué mostrar si no hay filas
}

const DEFAULT_SKELETON_ROWS = 5

function cellClassName<T>(column: DataTableColumn<T>): string {
  return cx(
    column.align === 'end' && 'ui-cell--end',
    column.align === 'center' && 'ui-cell--center',
    column.numeric && 'ui-cell--numeric',
  )
}

export function DataTable<T>({
  caption,
  columns,
  rows,
  getRowId,
  isLoading = false,
  skeletonRows = DEFAULT_SKELETON_ROWS,
  emptyState = <EmptyState title="Sin resultados" description="No hay datos para mostrar." />,
}: DataTableProps<T>) {
  const isEmpty = !isLoading && rows.length === 0

  return (
    // aria-busy informa a lectores de pantalla que el contenido se está actualizando.
    <div className="ui-table-wrap" aria-busy={isLoading || undefined}>
      <table className="ui-table">
        <caption className="ui-visually-hidden">{caption}</caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.id} scope="col" className={cellClassName(column)}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {isLoading &&
            // Filas esqueleto con la MISMA forma que las reales: sin saltos de layout al cargar.
            Array.from({ length: skeletonRows }, (_, rowIndex) => (
              <tr key={`skeleton-${rowIndex}`} data-testid="skeleton-row">
                {columns.map((column) => (
                  <td key={column.id}>
                    <span className="ui-skeleton" />
                  </td>
                ))}
              </tr>
            ))}

          {isEmpty && (
            <tr>
              {/* colSpan = todas las columnas: el estado vacío ocupa el ancho completo. */}
              <td colSpan={columns.length}>{emptyState}</td>
            </tr>
          )}

          {!isLoading &&
            rows.map((row) => (
              <tr key={getRowId(row)}>
                {columns.map((column) => (
                  <td key={column.id} className={cellClassName(column)}>
                    {column.cell(row)}
                  </td>
                ))}
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  )
}
