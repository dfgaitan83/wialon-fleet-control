"""Catálogo de permisos y matriz de roles (RF-05, matriz 5.3 del enunciado).

¿Por qué permisos granulares y no ``if role == "admin"``?
- El enunciado lo exige ("permisos granulares por rol", no ifs regados).
- Abierto/cerrado: un rol nuevo (p. ej. "Supervisor") es una fila de datos en la
  BD, sin tocar ni una línea de los endpoints, que solo preguntan por PERMISOS.
- El frontend usa los mismos nombres (``frontend/src/app/navigation.ts``).

Formato ``"recurso:acción"``. Este módulo es la fuente de verdad del CÓDIGO; la
migración ``0002`` guarda una copia congelada (las migraciones no deben cambiar
si este archivo cambia después) y un test vigila que ambas coincidan.
"""

from enum import StrEnum


class Permission(StrEnum):
    """Permisos de la aplicación. ``StrEnum``: se compara y serializa como texto."""

    DASHBOARD_READ = "dashboard:read"  # KPIs del panel (RF-23)
    VEHICLES_READ = "vehicles:read"  # lista, mapa y detalle (RF-10..15)
    VEHICLES_WRITE = "vehicles:write"  # campos personalizados de vehículos (RF-19..22)
    DRIVERS_READ = "drivers:read"
    DRIVERS_WRITE = "drivers:write"  # crear, editar y eliminar conductores (RF-16, RF-18)
    PASSENGERS_READ = "passengers:read"
    PASSENGERS_WRITE = "passengers:write"  # CRUD + campos personalizados (RF-08, RF-27, RF-28)
    ASSIGNMENTS_WRITE = "assignments:write"  # vincular/desvincular conductor y pasajero (RF-09, RF-17)
    HISTORY_READ = "history:read"  # historial de recorridos (RF-24)
    EXPORT_CSV = "export:csv"  # exportaciones CSV (RF-25)
    USERS_READ = "users:read"  # ver usuarios (RF-06)
    USERS_WRITE = "users:write"  # crear, cambiar rol, activar/desactivar, restablecer (RF-06)
    AUDIT_READ = "audit:read"  # registro de auditoría (RF-26)


class RoleName(StrEnum):
    """Roles mínimos del enunciado. Más roles = más filas en la BD, no más código."""

    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


# Lo que TODOS los roles pueden ver (filas "Sí / Sí / Sí" de la matriz 5.3).
_READ_ONLY: frozenset[Permission] = frozenset(
    {
        Permission.DASHBOARD_READ,
        Permission.VEHICLES_READ,
        Permission.DRIVERS_READ,
        Permission.PASSENGERS_READ,
        Permission.HISTORY_READ,
    }
)

# Operador = lectura + escrituras de flota + CSV (filas "Sí / Sí / No").
_OPERATOR: frozenset[Permission] = _READ_ONLY | {
    Permission.VEHICLES_WRITE,
    Permission.DRIVERS_WRITE,
    Permission.PASSENGERS_WRITE,
    Permission.ASSIGNMENTS_WRITE,
    Permission.EXPORT_CSV,
}

# Matriz 5.3 completa. Admin recibe TODOS los permisos explícitos (sin comodín "*:*":
# así cada permiso del Admin es visible y auditable en la BD).
ROLE_PERMISSIONS: dict[RoleName, frozenset[Permission]] = {
    RoleName.ADMIN: frozenset(Permission),
    RoleName.OPERATOR: _OPERATOR,
    RoleName.VIEWER: _READ_ONLY,
}

# Nombres visibles en la interfaz (es-CO).
ROLE_LABELS: dict[RoleName, str] = {
    RoleName.ADMIN: "Administrador",
    RoleName.OPERATOR: "Operador",
    RoleName.VIEWER: "Visualizador",
}
