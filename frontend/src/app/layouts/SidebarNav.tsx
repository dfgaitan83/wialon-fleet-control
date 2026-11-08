/**
 * Menú lateral del panel. Responsabilidad única: PINTAR las entradas que recibe.
 * No decide qué entradas mostrar (eso lo hace useVisibleNavigation) -> es reutilizable
 * y se prueba pasándole cualquier lista.
 */
import { NavLink } from 'react-router-dom'

import { type NavItem, navItemPath } from '../navigation'

interface SidebarNavProps {
  readonly items: readonly NavItem[]
}

export function SidebarNav({ items }: SidebarNavProps) {
  return (
    <nav aria-label="Principal" className="sidebar-nav">
      <ul>
        {items.map((item) => (
          <li key={item.segment || 'home'}>
            <NavLink
              to={navItemPath(item)}
              // end: "/app" solo se marca activo en "/app", no en "/app/vehicles".
              end={item.segment === ''}
              // NavLink añade aria-current="page" al enlace activo (lo leen los lectores de pantalla).
              className={({ isActive }) => (isActive ? 'sidebar-link sidebar-link--active' : 'sidebar-link')}
            >
              <item.icon />
              <span>{item.label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
