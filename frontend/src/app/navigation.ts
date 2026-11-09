/**
 * Navegación del panel: ÚNICA fuente de verdad para el MENÚ y las RUTAS privadas.
 *
 * SOLID — Abierto/Cerrado (O): para añadir un módulo se agrega UNA entrada aquí.
 * El router (router.tsx) y el menú (SidebarNav.tsx) se generan a partir de esta
 * lista: no hay que modificarlos (abiertos a extensión, cerrados a modificación).
 *
 * Cada entrada declara el PERMISO que exige; así el menú oculta lo que no puedes
 * usar y la ruta queda protegida con <RequirePermission> (doble capa en la UI;
 * la seguridad real la aplica el backend con require_permission).
 *
 * Nombres de permiso: supuesto alineado con el RBAC que implementará el backend (M2).
 */
import type { ComponentType } from 'react'

import { UsersPage } from '@/features/users/UsersPage'
import type { Permission } from '@/shared/auth/types'

import {
  AuditIcon,
  DashboardIcon,
  DriverIcon,
  HistoryIcon,
  PassengersIcon,
  UsersIcon,
  VehicleIcon,
} from './components/NavIcons'

export const APP_BASE_PATH = '/app' // prefijo de todas las rutas privadas

export interface NavItem {
  readonly segment: string // tramo de URL bajo /app ("" = página inicial del panel)
  readonly label: string // texto del menú y título de la página
  readonly permission: Permission // permiso necesario para verlo
  readonly icon: ComponentType // icono del menú
  readonly milestone: string // meta del plan en la que se construye (se muestra mientras tanto)
  readonly page?: ComponentType // página real; si falta, se muestra "en construcción"
}

export const APP_NAVIGATION: readonly NavItem[] = [
  { segment: '', label: 'Resumen', permission: 'dashboard:read', icon: DashboardIcon, milestone: 'M7' },
  { segment: 'vehicles', label: 'Vehículos', permission: 'vehicles:read', icon: VehicleIcon, milestone: 'M7' },
  { segment: 'drivers', label: 'Conductores', permission: 'drivers:read', icon: DriverIcon, milestone: 'M7' },
  { segment: 'passengers', label: 'Pasajeros', permission: 'passengers:read', icon: PassengersIcon, milestone: 'M7' },
  { segment: 'history', label: 'Historial', permission: 'history:read', icon: HistoryIcon, milestone: 'M7' },
  { segment: 'users', label: 'Usuarios', permission: 'users:read', icon: UsersIcon, milestone: 'M7', page: UsersPage },
  { segment: 'audit', label: 'Auditoría', permission: 'audit:read', icon: AuditIcon, milestone: 'M7' },
]

/** URL absoluta de una entrada: "" -> "/app", "vehicles" -> "/app/vehicles". */
export function navItemPath(item: NavItem): string {
  return item.segment ? `${APP_BASE_PATH}/${item.segment}` : APP_BASE_PATH
}

/**
 * Entradas visibles para un usuario. Función PURA (sin React): fácil de probar.
 * Recibe la función de permisos en vez del usuario -> no depende de cómo se
 * calculan los permisos (Inversión de dependencias en pequeño).
 */
export function filterNavigation(
  items: readonly NavItem[],
  can: (permission: Permission) => boolean,
): readonly NavItem[] {
  return items.filter((item) => can(item.permission)) // filter devuelve un array NUEVO
}
