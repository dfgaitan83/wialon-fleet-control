/**
 * Acciones sobre una persona: editar, asignar/desasignar vehículo (RF-09, RF-17) y
 * eliminar. Lo destructivo pide confirmación en línea (UX-04). Cada botón aparece solo
 * con su permiso; el backend lo vuelve a exigir.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useId, useState } from 'react'

import { ApiError } from '@/shared/api/problem'
import { Button } from '@/shared/ui/Button'

import { peopleApi, peopleKeys, type Person, type PersonKind } from './peopleApi'

type Mode = 'idle' | 'assign' | 'delete'

interface PersonRowActionsProps {
  readonly kind: PersonKind
  readonly person: Person
  readonly vehicles: ReadonlyArray<{ id: number; name: string }>
  readonly canWrite: boolean
  readonly canAssign: boolean
  readonly onEdit: (person: Person) => void
  readonly onResult: (message: string, isError?: boolean) => void
}

const errorText = (error: unknown) => (error instanceof ApiError ? error.message : 'No se pudo completar la acción.')

export function PersonRowActions({ kind, person, vehicles, canWrite, canAssign, onEdit, onResult }: PersonRowActionsProps) {
  const id = useId()
  const queryClient = useQueryClient()
  const [mode, setMode] = useState<Mode>('idle')
  const [vehicleId, setVehicleId] = useState<number | ''>('')

  const done = (message: string) => {
    void queryClient.invalidateQueries({ queryKey: peopleKeys.all(kind) })
    void queryClient.invalidateQueries({ queryKey: ['fleet'] })
    setMode('idle')
    onResult(message)
  }
  const fail = (error: unknown) => onResult(errorText(error), true)

  const assign = useMutation({
    mutationFn: (target: number) => peopleApi.assign(kind, person, target),
    onSuccess: (_, target) => done(`${person.name} asignado a ${vehicles.find((v) => v.id === target)?.name ?? 'el vehículo'}.`),
    onError: fail,
  })
  const unassign = useMutation({
    mutationFn: () => peopleApi.unassign(kind, person, person.vehicle!.id),
    onSuccess: () => done(`${person.name} desasignado de ${person.vehicle?.name}.`),
    onError: fail,
  })
  const remove = useMutation({
    mutationFn: () => peopleApi.remove(kind, person),
    onSuccess: () => done(`${person.name} eliminado de Wialon.`),
    onError: fail,
  })
  const busy = assign.isPending || unassign.isPending || remove.isPending

  if (mode === 'assign') {
    return (
      <div className="people-inline" role="group" aria-label={`Asignar vehículo a ${person.name}`}>
        <label className="ui-visually-hidden" htmlFor={`${id}-v`}>
          Vehículo
        </label>
        <select id={`${id}-v`} className="ui-field__input" value={vehicleId} onChange={(e) => setVehicleId(Number(e.target.value) || '')}>
          <option value="">Elige un vehículo…</option>
          {vehicles.map((v) => (
            <option key={v.id} value={v.id}>
              {v.name}
            </option>
          ))}
        </select>
        <Button size="sm" variant="primary" isLoading={busy} disabled={vehicleId === ''} onClick={() => vehicleId !== '' && assign.mutate(vehicleId)}>
          Asignar
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setMode('idle')} disabled={busy}>
          Cancelar
        </Button>
      </div>
    )
  }

  if (mode === 'delete') {
    return (
      <div className="people-inline" role="group" aria-label="Confirmar eliminación">
        <span>¿Eliminar a {person.name} de Wialon?</span>
        <Button size="sm" variant="danger" isLoading={busy} onClick={() => remove.mutate()}>
          Eliminar
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setMode('idle')} disabled={busy}>
          Cancelar
        </Button>
      </div>
    )
  }

  return (
    <div className="people-inline">
      {canWrite && (
        <Button size="sm" onClick={() => onEdit(person)} disabled={busy}>
          Editar
        </Button>
      )}
      {canAssign &&
        (person.vehicle ? (
          <Button size="sm" isLoading={unassign.isPending} onClick={() => unassign.mutate()}>
            Desasignar
          </Button>
        ) : (
          <Button size="sm" onClick={() => setMode('assign')} disabled={busy}>
            Asignar vehículo
          </Button>
        ))}
      {canWrite && (
        <Button size="sm" variant="ghost" onClick={() => setMode('delete')} disabled={busy}>
          Eliminar
        </Button>
      )}
    </div>
  )
}
