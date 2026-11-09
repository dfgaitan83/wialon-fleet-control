/**
 * Bloque de usuario de la barra superior: nombre, correo y "Cerrar sesión".
 * Responsabilidad única: mostrar la sesión actual y permitir cerrarla.
 */
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'

import { CHANGE_PASSWORD_PATH } from '@/shared/auth/types'
import { useAuth } from '@/shared/auth/useAuth'
import { Button } from '@/shared/ui/Button'
import { ButtonLink } from '@/shared/ui/ButtonLink'

import { initials } from './initials'

export function UserMenu() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  if (user === null) return null // AppLayout solo se monta con sesión; defensa por si acaso

  const handleLogout = async () => {
    // ORDEN IMPORTANTE: primero salir de /app y DESPUÉS cerrar la sesión. Al revés,
    // RequireAuth (aún en /app) vería "anonymous" y redirigiría a /login en vez de
    // a la landing (carrera detectada por router.test.tsx).
    await navigate('/', { replace: true }) // replace: el panel no queda en el historial
    await logout() // el servidor invalida la sesión (no basta con olvidarla en el navegador)
    queryClient.clear() // nadie que entre después en este navegador ve datos del usuario anterior
  }

  return (
    <div className="user-menu">
      <span className="user-menu__avatar" aria-hidden="true">
        {initials(user.fullName)}
      </span>
      <span className="user-menu__identity">
        <span className="user-menu__name">{user.fullName}</span>
        <span className="user-menu__email">{user.email}</span>
      </span>
      <ButtonLink variant="ghost" size="sm" to={CHANGE_PASSWORD_PATH}>
        Cambiar contraseña
      </ButtonLink>
      <Button variant="ghost" size="sm" onClick={handleLogout}>
        Cerrar sesión
      </Button>
    </div>
  )
}
