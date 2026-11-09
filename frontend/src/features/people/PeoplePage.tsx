/**
 * Conductores y Pasajeros (una sola pantalla parametrizada por tipo: DRY).
 * Lista con búsqueda, filtro con/sin vehículo y paginación del SERVIDOR (RF-28),
 * alta/edición con campos personalizados (RF-27), asignación a vehículos (RF-09, RF-17).
 * Todo se guarda en Wialon y se lee de Wialon (RF-08, RF-16).
 */
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'

import { fleetApi } from '@/features/vehicles/fleetApi'
import { useAuth } from '@/shared/auth/useAuth'
import { Button } from '@/shared/ui/Button'
import { DataTable, type DataTableColumn } from '@/shared/ui/DataTable'
import { EmptyState } from '@/shared/ui/EmptyState'

import { KIND_TEXT, peopleApi, peopleKeys, type PeopleQuery, type Person, type PersonKind } from './peopleApi'
import { PersonForm } from './PersonForm'
import { PersonRowActions } from './PersonRowActions'
import './people.css'

const PAGE_SIZE = 12
const VEHICLE_PAGE_SIZE = 100 // la cuenta tiene 62: una sola página para el selector

interface Notice {
  readonly message: string
  readonly isError: boolean
}

function PeoplePage({ kind }: { readonly kind: PersonKind }) {
  const text = KIND_TEXT[kind]
  const { hasPermission } = useAuth()
  const canWrite = hasPermission(text.write)
  const canAssign = hasPermission('assignments:write')
  const [query, setQuery] = useState<PeopleQuery>({ page: 1, pageSize: PAGE_SIZE, search: '', assigned: '' })
  const [editing, setEditing] = useState<Person | 'new' | null>(null)
  const [notice, setNotice] = useState<Notice | null>(null)

  const people = useQuery({
    queryKey: peopleKeys.list(kind, query),
    queryFn: () => peopleApi.list(kind, query),
    placeholderData: keepPreviousData,
  })
  const vehicles = useQuery({
    queryKey: ['fleet', 'vehicle-options'],
    queryFn: () => fleetApi.vehicles({ page: 1, pageSize: VEHICLE_PAGE_SIZE, search: '', status: '' }),
    enabled: canAssign,
    staleTime: 60_000,
  })
  const vehicleOptions = (vehicles.data?.items ?? []).map((v) => ({ id: v.id, name: v.name }))
  const totalPages = Math.max(1, Math.ceil((people.data?.total ?? 0) / PAGE_SIZE))
  const showNotice = (message: string, isError = false) => setNotice({ message, isError })

  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    setQuery((q) => ({
      ...q,
      page: 1,
      search: String(form.get('q') ?? '').trim(),
      assigned: String(form.get('assigned') ?? '') as PeopleQuery['assigned'],
    }))
  }

  const columns: DataTableColumn<Person>[] = [
    {
      id: 'name',
      header: text.singular === 'conductor' ? 'Conductor' : 'Pasajero',
      cell: (p) => (
        <span className="people-identity">
          <span className="people-identity__name">{p.name}</span>
          <span className="people-identity__meta">{[p.code, p.phone].filter(Boolean).join(' · ') || 'Sin código'}</span>
        </span>
      ),
    },
    {
      id: 'fields',
      header: 'Campos',
      cell: (p) => {
        const entries = Object.entries(p.customFields)
        if (entries.length === 0) return <span className="people-muted">—</span>
        return (
          <ul className="people-chips" aria-label="Campos personalizados">
            {entries.slice(0, 3).map(([k, v]) => (
              <li key={k} className="people-chip">
                {k}: {v || '—'}
              </li>
            ))}
            {entries.length > 3 && <li className="people-chip">+{entries.length - 3}</li>}
          </ul>
        )
      },
    },
    {
      id: 'vehicle',
      header: 'Vehículo',
      cell: (p) =>
        p.vehicle ? (
          <Link to={`/app/vehicles/${p.vehicle.id}`}>{p.vehicle.name}</Link>
        ) : (
          <span className="people-muted">Sin vehículo</span>
        ),
    },
    ...(canWrite || canAssign
      ? [
          {
            id: 'actions',
            header: 'Acciones',
            cell: (p: Person) => (
              <PersonRowActions
                kind={kind}
                person={p}
                vehicles={vehicleOptions}
                canWrite={canWrite}
                canAssign={canAssign}
                onEdit={(person) => setEditing(person)}
                onResult={showNotice}
              />
            ),
          },
        ]
      : []),
  ]

  return (
    <section aria-labelledby="page-title">
      <header className="page-header people-header">
        <div>
          <p className="page-eyebrow">Sincronizado con Wialon</p>
          <h1 id="page-title" className="page-title">
            {text.plural}
          </h1>
          <p className="page-subtitle">
            {people.data ? `${people.data.total} ${text.plural.toLowerCase()} en la cuenta.` : 'Cargando…'}
          </p>
        </div>
        {canWrite && editing === null && (
          <Button variant="primary" onClick={() => setEditing('new')}>
            + Nuevo {text.singular}
          </Button>
        )}
      </header>

      {notice && (
        <p className={notice.isError ? 'ui-alert' : 'ui-alert ui-alert--info'} role={notice.isError ? 'alert' : 'status'}>
          {notice.message}
        </p>
      )}

      {editing !== null && (
        <div className="page-card people-card">
          <PersonForm
            key={editing === 'new' ? 'new' : `${editing.resourceId}-${editing.id}`}
            kind={kind}
            person={editing === 'new' ? null : editing}
            onDone={(message) => {
              setEditing(null)
              showNotice(message)
            }}
            onCancel={() => setEditing(null)}
          />
        </div>
      )}

      <div className="page-card people-card">
        <form className="people-toolbar" role="search" onSubmit={handleSearch}>
          <label className="ui-visually-hidden" htmlFor={`${kind}-q`}>
            Buscar por nombre o código
          </label>
          <input id={`${kind}-q`} name="q" className="ui-field__input" placeholder="Buscar por nombre o código" />
          <label className="ui-visually-hidden" htmlFor={`${kind}-assigned`}>
            Filtrar por asignación
          </label>
          <select id={`${kind}-assigned`} name="assigned" className="ui-field__input people-toolbar__filter" defaultValue="">
            <option value="">Todos</option>
            <option value="true">Con vehículo</option>
            <option value="false">Sin vehículo</option>
          </select>
          <Button type="submit">Buscar</Button>
        </form>

        {people.isError ? (
          <EmptyState
            title={`No se pudieron cargar los ${text.plural.toLowerCase()}`}
            description={people.error instanceof Error ? people.error.message : 'Inténtalo de nuevo.'}
            action={<Button onClick={() => void people.refetch()}>Reintentar</Button>}
          />
        ) : (
          <DataTable
            caption={text.plural}
            columns={columns}
            rows={people.data?.items ?? []}
            getRowId={(p) => `${p.resourceId}-${p.id}`}
            isLoading={people.isPending}
            emptyState={
              <EmptyState
                title={query.search || query.assigned ? 'Sin coincidencias' : `Aún no hay ${text.plural.toLowerCase()}`}
                description={
                  query.search || query.assigned ? 'Prueba con otra búsqueda o quita el filtro.' : `Crea el primero con “Nuevo ${text.singular}”.`
                }
              />
            }
          />
        )}

        <nav className="people-pagination" aria-label={`Paginación de ${text.plural.toLowerCase()}`}>
          <Button size="sm" disabled={query.page <= 1} onClick={() => setQuery((q) => ({ ...q, page: q.page - 1 }))}>
            Anterior
          </Button>
          <span aria-live="polite">
            Página {query.page} de {totalPages}
          </span>
          <Button size="sm" disabled={query.page >= totalPages} onClick={() => setQuery((q) => ({ ...q, page: q.page + 1 }))}>
            Siguiente
          </Button>
        </nav>
      </div>
    </section>
  )
}

export const DriversPage = () => <PeoplePage kind="drivers" />
export const PassengersPage = () => <PeoplePage kind="passengers" />
