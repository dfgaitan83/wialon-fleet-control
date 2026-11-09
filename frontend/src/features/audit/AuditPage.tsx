/**
 * Registro de auditoría (RF-26, solo Admin): quién hizo qué y cuándo.
 * Altas/ediciones/bajas de conductores y pasajeros, asignaciones, gestión de usuarios,
 * inicios de sesión (incluidos los fallidos) y accesos denegados. Hora de Bogotá.
 */
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { z } from 'zod'

import { apiClient } from '@/shared/api/client'
import { ApiError } from '@/shared/api/problem'
import { formatDateTime } from '@/shared/format'
import { Button } from '@/shared/ui/Button'
import { DataTable, type DataTableColumn } from '@/shared/ui/DataTable'
import { EmptyState } from '@/shared/ui/EmptyState'
import { StatusBadge, type StatusTone } from '@/shared/ui/StatusBadge'

import './audit.css'

const PAGE_SIZE = 20

const entrySchema = z.object({
  action: z.string(),
  occurred_at: z.iso.datetime({ offset: true }).transform((v) => new Date(v)),
  actor_email: z.string().nullable(),
  entity_type: z.string().nullable(),
  entity_id: z.string().nullable(),
  ip_address: z.string().nullable(),
  details: z.record(z.string(), z.unknown()).nullable(),
})
const pageSchema = z.object({ items: z.array(entrySchema), total: z.number() })
type Entry = z.infer<typeof entrySchema>

// Acción técnica -> texto en español + color semántico (el color NUNCA va solo: siempre con texto).
const ACTIONS: Record<string, { label: string; tone: StatusTone }> = {
  'auth.login_succeeded': { label: 'Inicio de sesión', tone: 'success' },
  'auth.login_failed': { label: 'Inicio de sesión fallido', tone: 'danger' },
  'auth.account_locked': { label: 'Cuenta bloqueada', tone: 'danger' },
  'auth.logout': { label: 'Cierre de sesión', tone: 'neutral' },
  'auth.password_changed': { label: 'Cambio de contraseña', tone: 'info' },
  'auth.access_denied': { label: 'Acceso denegado', tone: 'warning' },
  'auth.refresh_reuse_detected': { label: 'Posible robo de sesión', tone: 'danger' },
  'auth.admin_password_reset_cli': { label: 'Recuperación de Admin', tone: 'warning' },
  'users.created': { label: 'Usuario creado', tone: 'success' },
  'users.updated': { label: 'Usuario modificado', tone: 'info' },
  'users.password_reset': { label: 'Contraseña restablecida', tone: 'warning' },
}
const VERBS: Record<string, string> = {
  created: 'creado', updated: 'editado', deleted: 'eliminado', assigned: 'asignado', unassigned: 'desasignado',
}
const TONES: Record<string, StatusTone> = { created: 'success', updated: 'info', deleted: 'danger', assigned: 'info', unassigned: 'neutral' }

function describe(action: string): { label: string; tone: StatusTone } {
  if (ACTIONS[action]) return ACTIONS[action]
  const [entity, verb] = action.split('.')
  const noun = entity === 'drivers' ? 'Conductor' : entity === 'passengers' ? 'Pasajero' : entity
  return { label: `${noun} ${VERBS[verb] ?? verb}`, tone: TONES[verb] ?? 'neutral' }
}

/** Detalle legible (sin JSON crudo): "motivo: wrong_password · vehículo: Bus 1". */
function detailText(entry: Entry): string {
  if (!entry.details) return ''
  return Object.entries(entry.details)
    .map(([key, value]) => `${key}: ${typeof value === 'object' ? JSON.stringify(value) : String(value)}`)
    .join(' · ')
}

async function fetchAudit(page: number, category: string, q: string) {
  const { data } = await apiClient.get<unknown>('/audit', {
    params: { page, page_size: PAGE_SIZE, category: category || undefined, q: q || undefined },
  })
  const parsed = pageSchema.safeParse(data)
  if (!parsed.success) throw new ApiError(502, 'El servidor respondió en un formato inesperado.')
  return parsed.data
}

export function AuditPage() {
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({ category: '', q: '' })
  const audit = useQuery({
    queryKey: ['audit', page, filters],
    queryFn: () => fetchAudit(page, filters.category, filters.q),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
  })
  const totalPages = Math.max(1, Math.ceil((audit.data?.total ?? 0) / PAGE_SIZE))

  const handleFilter = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    setFilters({ category: String(form.get('category') ?? ''), q: String(form.get('q') ?? '').trim() })
    setPage(1)
  }

  const columns: DataTableColumn<Entry>[] = [
    {
      id: 'when',
      header: 'Fecha (hora Colombia)',
      cell: (e) => <time dateTime={e.occurred_at.toISOString()}>{formatDateTime(e.occurred_at)}</time>,
    },
    { id: 'action', header: 'Evento', cell: (e) => <StatusBadge {...describe(e.action)} /> },
    { id: 'actor', header: 'Quién', cell: (e) => e.actor_email ?? <span className="audit-muted">Anónimo</span> },
    { id: 'detail', header: 'Detalle', cell: (e) => <span className="audit-detail">{detailText(e) || '—'}</span> },
    { id: 'ip', header: 'IP', cell: (e) => <span className="audit-muted">{e.ip_address ?? '—'}</span> },
  ]

  return (
    <section aria-labelledby="page-title">
      <header className="page-header">
        <p className="page-eyebrow">Administración</p>
        <h1 id="page-title" className="page-title">
          Auditoría
        </h1>
        <p className="page-subtitle">Quién hizo qué y cuándo, incluidos los intentos de acceso fallidos.</p>
      </header>

      <div className="page-card audit-card">
        <form className="audit-toolbar" role="search" onSubmit={handleFilter}>
          <label className="ui-visually-hidden" htmlFor="audit-category">
            Categoría
          </label>
          <select id="audit-category" name="category" className="ui-field__input audit-toolbar__category" defaultValue="">
            <option value="">Todos los eventos</option>
            <option value="auth">Accesos y sesiones</option>
            <option value="users">Usuarios</option>
            <option value="drivers">Conductores</option>
            <option value="passengers">Pasajeros</option>
          </select>
          <label className="ui-visually-hidden" htmlFor="audit-q">
            Buscar por correo
          </label>
          <input id="audit-q" name="q" className="ui-field__input" placeholder="Buscar por correo de quien actuó" />
          <Button type="submit">Filtrar</Button>
        </form>

        {audit.isError ? (
          <EmptyState
            title="No se pudo cargar la auditoría"
            description={audit.error instanceof Error ? audit.error.message : 'Inténtalo de nuevo.'}
            action={<Button onClick={() => void audit.refetch()}>Reintentar</Button>}
          />
        ) : (
          <DataTable
            caption="Registro de auditoría"
            columns={columns}
            rows={audit.data?.items ?? []}
            getRowId={(e) => `${e.occurred_at.getTime()}-${e.action}-${e.entity_id ?? ''}-${e.actor_email ?? ''}`}
            isLoading={audit.isPending}
            emptyState={<EmptyState title="Sin eventos" description="Aún no hay actividad con estos filtros." />}
          />
        )}

        <nav className="audit-pagination" aria-label="Paginación de auditoría">
          <Button size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            Anterior
          </Button>
          <span aria-live="polite">
            Página {page} de {totalPages} · {audit.data?.total ?? 0} eventos
          </span>
          <Button size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
            Siguiente
          </Button>
        </nav>
      </div>
    </section>
  )
}
