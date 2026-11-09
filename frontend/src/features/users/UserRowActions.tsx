/**
 * Acciones del Admin sobre UN usuario: cambiar rol, activar/desactivar y restablecer.
 * Las acciones destructivas piden confirmación en línea (UX-04). Sobre sí mismo, el
 * Admin no puede cambiar su rol ni desactivarse (el backend también lo impide: 409).
 */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { ApiError } from '@/shared/api/problem'
import { Button } from '@/shared/ui/Button'

import { type ManagedUser, type Role, usersApi, usersKeys } from './usersApi'

type PendingAction = 'toggle' | 'reset' | null

interface UserRowActionsProps {
  readonly user: ManagedUser
  readonly roles: readonly Role[]
  readonly isSelf: boolean
  readonly onPasswordReset: (user: ManagedUser, temporaryPassword: string) => void
  readonly onError: (message: string) => void
}

const errorMessage = (error: unknown) =>
  error instanceof ApiError ? error.message : 'No se pudo completar la acción.'

export function UserRowActions({ user, roles, isSelf, onPasswordReset, onError }: UserRowActionsProps) {
  const queryClient = useQueryClient()
  const [pending, setPending] = useState<PendingAction>(null)
  const refresh = () => void queryClient.invalidateQueries({ queryKey: usersKeys.all })

  const update = useMutation({
    mutationFn: (changes: { role?: string; isActive?: boolean }) => usersApi.update(user.id, changes),
    onSuccess: refresh,
    onError: (error) => onError(errorMessage(error)),
    onSettled: () => setPending(null),
  })
  const reset = useMutation({
    mutationFn: () => usersApi.resetPassword(user.id),
    onSuccess: (password) => {
      refresh()
      onPasswordReset(user, password)
    },
    onError: (error) => onError(errorMessage(error)),
    onSettled: () => setPending(null),
  })
  const busy = update.isPending || reset.isPending

  if (pending !== null) {
    const question =
      pending === 'reset'
        ? `¿Generar una contraseña temporal para ${user.fullName}? Se cerrarán sus sesiones.`
        : `¿${user.isActive ? 'Desactivar' : 'Activar'} a ${user.fullName}?`
    return (
      <div className="users-confirm" role="group" aria-label="Confirmar acción">
        <span>{question}</span>
        <Button
          size="sm"
          variant="danger"
          isLoading={busy}
          onClick={() => (pending === 'reset' ? reset.mutate() : update.mutate({ isActive: !user.isActive }))}
        >
          Confirmar
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setPending(null)} disabled={busy}>
          Cancelar
        </Button>
      </div>
    )
  }

  return (
    <div className="users-actions">
      <label className="ui-visually-hidden" htmlFor={`role-${user.id}`}>
        Rol de {user.fullName}
      </label>
      <select
        id={`role-${user.id}`}
        className="ui-field__input users-actions__role"
        value={user.role}
        disabled={isSelf || busy}
        title={isSelf ? 'No puedes cambiar tu propio rol' : undefined}
        onChange={(event) => update.mutate({ role: event.target.value })}
      >
        {roles.map((role) => (
          <option key={role.name} value={role.name}>
            {role.label}
          </option>
        ))}
      </select>
      <Button size="sm" onClick={() => setPending('toggle')} disabled={isSelf || busy}>
        {user.isActive ? 'Desactivar' : 'Activar'}
      </Button>
      <Button size="sm" variant="ghost" onClick={() => setPending('reset')} disabled={busy}>
        Restablecer contraseña
      </Button>
    </div>
  )
}
