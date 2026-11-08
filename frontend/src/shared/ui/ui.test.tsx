/**
 * Tests de los componentes base: se verifica COMPORTAMIENTO y accesibilidad
 * (lo que ve/usa la persona), no detalles de implementación.
 */
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { VehicleStatusBadge } from '@/features/vehicles/components/VehicleStatusBadge'

import { Button } from './Button'
import { DataTable, type DataTableColumn } from './DataTable'
import { EmptyState } from './EmptyState'
import { StatusBadge } from './StatusBadge'

describe('Button', () => {
  it('por defecto es type="button" (no envía formularios sin querer)', () => {
    render(<Button>Guardar</Button>)

    expect(screen.getByRole('button', { name: 'Guardar' })).toHaveAttribute('type', 'button')
  })

  it('ejecuta onClick al pulsarlo', async () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Guardar</Button>)

    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(onClick).toHaveBeenCalledOnce()
  })

  it('isLoading lo desactiva y anuncia "ocupado" -> evita el doble envío', async () => {
    const onClick = vi.fn()
    render(
      <Button isLoading onClick={onClick}>
        Guardar
      </Button>,
    )
    const button = screen.getByRole('button', { name: 'Guardar' })

    await userEvent.click(button)

    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    expect(onClick).not.toHaveBeenCalled()
  })

  it('aplica la clase de la variante', () => {
    render(<Button variant="danger">Eliminar</Button>)

    expect(screen.getByRole('button', { name: 'Eliminar' })).toHaveClass('ui-button', 'ui-button--danger')
  })
})

describe('StatusBadge / VehicleStatusBadge', () => {
  it('siempre muestra texto (el color no es el único portador del significado)', () => {
    render(<StatusBadge tone="success" label="Activo" />)

    expect(screen.getByText('Activo')).toHaveClass('ui-badge--success')
  })

  it.each([
    ['moving', 'En movimiento', 'ui-badge--success'],
    ['stopped', 'Detenido', 'ui-badge--warning'],
    ['unknown', 'Sin datos', 'ui-badge--info'],
  ] as const)('vehículo "%s" se muestra como "%s"', (status, label, className) => {
    render(<VehicleStatusBadge status={status} />)

    expect(screen.getByText(label)).toHaveClass(className)
  })

  it('solo "en movimiento" tiene la animación de señal viva', () => {
    render(
      <>
        <VehicleStatusBadge status="moving" />
        <VehicleStatusBadge status="offline" />
      </>,
    )

    expect(screen.getByText('En movimiento')).toHaveClass('ui-badge--pulse')
    expect(screen.getByText('Sin conexión')).not.toHaveClass('ui-badge--pulse')
  })
})

describe('DataTable', () => {
  interface Row {
    id: string
    name: string
    speed: number
  }
  const columns: DataTableColumn<Row>[] = [
    { id: 'name', header: 'Vehículo', cell: (r) => r.name },
    { id: 'speed', header: 'Velocidad', cell: (r) => `${r.speed} km/h`, align: 'end', numeric: true },
  ]
  const rows: Row[] = [
    { id: 'a', name: 'FSU778', speed: 0 },
    { id: 'b', name: 'GUV875', speed: 5 },
  ]

  it('pinta una fila por elemento con sus celdas', () => {
    render(<DataTable caption="Vehículos" columns={columns} rows={rows} getRowId={(r) => r.id} />)

    const table = screen.getByRole('table', { name: 'Vehículos' }) // caption = nombre accesible
    const bodyRows = within(table).getAllByRole('row').slice(1) // [0] es la cabecera
    expect(bodyRows).toHaveLength(2)
    expect(within(bodyRows[1]).getByText('5 km/h')).toHaveClass('ui-cell--end', 'ui-cell--numeric')
  })

  it('las cabeceras tienen scope="col" (navegación con lector de pantalla)', () => {
    render(<DataTable caption="Vehículos" columns={columns} rows={rows} getRowId={(r) => r.id} />)

    expect(screen.getByRole('columnheader', { name: 'Vehículo' })).toHaveAttribute('scope', 'col')
  })

  it('mientras carga muestra filas esqueleto y marca aria-busy', () => {
    const { container } = render(
      <DataTable caption="Vehículos" columns={columns} rows={[]} getRowId={(r) => r.id} isLoading skeletonRows={3} />,
    )

    expect(screen.getAllByTestId('skeleton-row')).toHaveLength(3)
    expect(container.querySelector('.ui-table-wrap')).toHaveAttribute('aria-busy', 'true')
    expect(screen.queryByText('Sin resultados')).not.toBeInTheDocument() // no confundir "cargando" con "vacío"
  })

  it('sin filas muestra el estado vacío (por defecto o personalizado)', () => {
    render(
      <DataTable
        caption="Vehículos"
        columns={columns}
        rows={[]}
        getRowId={(r) => r.id}
        emptyState={<EmptyState title="Sin vehículos" description="La cuenta no tiene unidades." />}
      />,
    )

    expect(screen.getByText('Sin vehículos')).toBeInTheDocument()
    expect(screen.getByText('La cuenta no tiene unidades.')).toBeInTheDocument()
  })
})
