"""Siembra los permisos y los roles Admin / Operador / Visualizador (matriz 5.3).

Copia CONGELADA de ``app/domain/permissions.py`` a propósito: una migración ya
aplicada no debe cambiar si el código cambia después. Si la matriz evoluciona,
se escribe una migración NUEVA. ``tests/unit/test_migrations.py`` vigila que
esta copia y el dominio coincidan.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS: dict[str, str] = {
    "dashboard:read": "Ver el panel de KPIs",
    "vehicles:read": "Ver vehículos, mapa y detalle",
    "vehicles:write": "Editar campos personalizados de vehículos",
    "drivers:read": "Ver conductores",
    "drivers:write": "Crear, editar y eliminar conductores",
    "passengers:read": "Ver pasajeros",
    "passengers:write": "Crear, editar y eliminar pasajeros y sus campos",
    "assignments:write": "Vincular y desvincular conductores y pasajeros",
    "history:read": "Ver historial de recorridos",
    "export:csv": "Exportar datos a CSV",
    "users:read": "Ver usuarios",
    "users:write": "Gestionar usuarios y roles",
    "audit:read": "Ver el registro de auditoría",
}

_READ_ONLY = ["dashboard:read", "vehicles:read", "drivers:read", "passengers:read", "history:read"]
_OPERATOR = [
    *_READ_ONLY,
    "vehicles:write",
    "drivers:write",
    "passengers:write",
    "assignments:write",
    "export:csv",
]

ROLES: dict[str, tuple[str, list[str]]] = {
    "admin": ("Administrador", list(PERMISSIONS)),
    "operator": ("Operador", _OPERATOR),
    "viewer": ("Visualizador", _READ_ONLY),
}

_permissions = sa.table(
    "permissions", sa.column("id", sa.Integer), sa.column("code", sa.String), sa.column("description", sa.String)
)
_roles = sa.table("roles", sa.column("id", sa.Integer), sa.column("name", sa.String), sa.column("label", sa.String))
_role_permissions = sa.table(
    "role_permissions", sa.column("role_id", sa.Integer), sa.column("permission_id", sa.Integer)
)


def upgrade() -> None:
    # Ids explícitos: la tabla puente se puede rellenar sin consultar lo recién insertado.
    permission_ids = {code: index for index, code in enumerate(PERMISSIONS, start=1)}
    op.bulk_insert(
        _permissions,
        [{"id": pid, "code": code, "description": PERMISSIONS[code]} for code, pid in permission_ids.items()],
    )
    role_ids = {name: index for index, name in enumerate(ROLES, start=1)}
    op.bulk_insert(_roles, [{"id": rid, "name": name, "label": ROLES[name][0]} for name, rid in role_ids.items()])
    op.bulk_insert(
        _role_permissions,
        [
            {"role_id": role_ids[name], "permission_id": permission_ids[code]}
            for name, (_label, codes) in ROLES.items()
            for code in codes
        ],
    )
    # PostgreSQL: avanzar las secuencias tras insertar ids explícitos (si no, el próximo
    # INSERT sin id chocaría con el 1). SQLite no tiene secuencias.
    if op.get_bind().dialect.name == "postgresql":
        for table in ("permissions", "roles"):
            op.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), (SELECT MAX(id) FROM {table}))")


def downgrade() -> None:
    op.execute(_role_permissions.delete())
    op.execute(_roles.delete())
    op.execute(_permissions.delete())
