/**
 * Gestión de usuarios (RF-06, solo Admin): listar, buscar, crear, cambiar rol,
 * activar/desactivar y restablecer credenciales.
 *
 * - Datos del servidor con TanStack Query (ARQ-10): caché + invalidación tras cada cambio.
 * - Paginación y búsqueda del lado del SERVIDOR (page, page_size, q).
 * - Estados de carga, vacío y error explícitos (ARQ-12).
 * - Las acciones de escritura solo aparecen con "users:write" (el backend lo exige igual).
 */
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'

import { RequirePermission } from '@/shared/auth/RequirePermission'
import { useAuth } from '@/shared/auth/useAuth'
import { Button } from '@/shared/ui/Button'
import { DataTable, type DataTableColumn } from '@/shared/ui/DataTable'
import { EmptyState } from '@/shared/ui/EmptyState'
import { StatusBadge } from '@/shared/ui/StatusBadge'

import { CreateUserForm } from './CreateUserForm'
import { TemporaryPasswordNotice } from './TemporaryPasswordNotice'
import { type ManagedUser, usersApi, usersKeys } from './usersApi'
import { UserRowActions } from './UserRowActions'
import './users.css'

const PAGE_SIZE = 10

interface Notice {
  readonly email: string
  readonly password: string
}

function AccountStatus({ user }: { readonly user: ManagedUser }) {
  if (!user.isActive) return <StatusBadge tone="neutral" label="Inactivo" />
  if (user.isLocked) return <StatusBadge tone="danger" label="Bloqueado" title="Demasiados intentos fallidos" />
  if (user.mustChangePassword) return <StatusBadge tone="warning" label="Debe cambiar contraseña" />
  return <StatusBadge tone="success" label="Activo" />
}

export function UsersPage() {
  const { user: me, hasPermission } = useAuth()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [notice, setNotice] = useState<Notice | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const users = useQuery({
    queryKey: usersKeys.list(page, search),
    queryFn: () => usersApi.list({ page, pageSize: PAGE_SIZE, search }),
    placeholderData: keepPreviousData, // al paginar se mantiene la tabla anterior (sin parpadeo)
  })
  const roles = useQuery({ queryKey: usersKeys.roles, queryFn: usersApi.roles, staleTime: Infinity })
  const roleList = roles.data ?? []
  const canWrite = hasPermission('users:write')
  const totalPages = Math.max(1, Math.ceil((users.data?.total ?? 0) / PAGE_SIZE))

  const showPassword = (user: ManagedUser, password: string) => {
    setActionError(null)
    setNotice({ email: user.email, password })
  }

  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSearch(String(new FormData(event.currentTarget).get('q') ?? '').trim())
    setPage(1) // una búsqueda nueva empieza en la primera página
  }

  const columns: DataTableColumn<ManagedUser>[] = [
    {
      id: 'name',
      header: 'Usuario',
      cell: (u) => (
        <span className="users-identity">
          <span className="users-identity__name">{u.fullName}</span>
          <span className="users-identity__email">{u.email}</span>
        </span>
      ),
    },
    { id: 'role', header: 'Rol', cell: (u) => u.roleLabel },
    { id: 'status', header: 'Estado', cell: (u) => <AccountStatus user={u} /> },
    ...(canWrite
      ? [
          {
            id: 'actions',
            header: 'Acciones',
            cell: (u: ManagedUser) => (
              <UserRowActions
                user={u}
                roles={roleList}
                isSelf={u.id === Number(me?.id)}
                onPasswordReset={showPassword}
                onError={setActionError}
              />
            ),
          },
        ]
      : []),
  ]

  return (
    <section aria-labelledby="page-title">
      <header className="page-header">
        <p className="page-eyebrow">Administración</p>
        <h1 id="page-title" className="page-title">
          Usuarios
        </h1>
        <p className="page-subtitle">Crea cuentas, asigna roles y gestiona el acceso a la plataforma.</p>
      </header>

      {notice && <TemporaryPasswordNotice {...notice} onClose={() => setNotice(null)} />}
      {actionError && (
        <p className="ui-alert" role="alert">
          {actionError}
        </p>
      )}

      <RequirePermission permission="users:write" fallback={null}>
        <div className="page-card users-card">
          <CreateUserForm roles={roleList} onCreated={showPassword} />
        </div>
      </RequirePermission>

      <div className="page-card users-card">
        <form className="users-toolbar" role="search" onSubmit={handleSearch}>
          <label className="ui-visually-hidden" htmlFor="users-search">
            Buscar por nombre o correo
          </label>
          <input id="users-search" name="q" className="ui-field__input" placeholder="Buscar por nombre o correo" />
          <Button type="submit">Buscar</Button>
        </form>

        {users.isError ? (
          <EmptyState
            title="No se pudieron cargar los usuarios"
            description={users.error instanceof Error ? users.error.message : 'Inténtalo de nuevo.'}
            action={<Button onClick={() => void users.refetch()}>Reintentar</Button>}
          />
        ) : (
          <DataTable
            caption="Usuarios de la plataforma"
            columns={columns}
            rows={users.data?.items ?? []}
            getRowId={(u) => String(u.id)}
            isLoading={users.isPending}
            emptyState={
              <EmptyState
                title={search ? 'Sin coincidencias' : 'Aún no hay usuarios'}
                description={search ? `Nadie coincide con "${search}".` : 'Crea el primero con el formulario de arriba.'}
              />
            }
          />
        )}

        <nav className="users-pagination" aria-label="Paginación de usuarios">
          <Button size="sm" onClick={() => setPage((p) => p - 1)} disabled={page <= 1 || users.isFetching}>
            Anterior
          </Button>
          <span aria-live="polite">
            Página {page} de {totalPages} · {users.data?.total ?? 0} usuarios
          </span>
          <Button size="sm" onClick={() => setPage((p) => p + 1)} disabled={page >= totalPages || users.isFetching}>
            Siguiente
          </Button>
        </nav>
      </div>
    </section>
  )
}
