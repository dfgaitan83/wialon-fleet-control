"""Tests de integración de la gestión de usuarios (RF-06) y su autorización (TST-02)."""

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from app.infrastructure.db.models import AuditLogModel
from tests.conftest import ADMIN_EMAIL, create_user, csrf_headers, login

NEW_EMAIL = "nuevo@flota.example.com"


async def _as_admin(app: FastAPI, client: httpx.AsyncClient) -> int:
    admin_id = await create_user(app, ADMIN_EMAIL)
    await login(client, ADMIN_EMAIL)
    return admin_id


async def _create(client: httpx.AsyncClient, email: str = NEW_EMAIL, role: str = "operator") -> httpx.Response:
    return await client.post(
        "/api/v1/users",
        json={"email": email, "full_name": "Nuevo Operador", "role": role},
        headers=csrf_headers(client),
    )


async def _audit_actions(app: FastAPI) -> list[str]:
    async with app.state.session_factory() as session:
        return list(await session.scalars(select(AuditLogModel.action).order_by(AuditLogModel.id)))


# --------------------------------------------------------- matriz TST-02

ENDPOINTS = [
    ("GET", "/api/v1/users"),
    ("GET", "/api/v1/roles"),
    ("GET", "/api/v1/users/1"),
    ("POST", "/api/v1/users"),
    ("PATCH", "/api/v1/users/1"),
    ("POST", "/api/v1/users/1/reset-password"),
]


@pytest.mark.parametrize(("method", "path"), ENDPOINTS)
@pytest.mark.parametrize(("role", "expected"), [("operator", 403), ("viewer", 403), (None, 401)])
async def test_only_admin_can_use_user_management(
    app: FastAPI, client: httpx.AsyncClient, method: str, path: str, role: str | None, expected: int
) -> None:
    # Sin sesión, una ESCRITURA se rechaza antes en el control CSRF (403) que en la
    # autenticación (401): el CSRF se valida primero, como en Django. Ambas niegan el acceso.
    if role is None and method != "GET":
        expected = 403
    await create_user(app, ADMIN_EMAIL)  # id 1: objetivo de los endpoints con {id}
    if role:
        await create_user(app, f"{role}@flota.example.com", role=role)
        await login(client, f"{role}@flota.example.com")

    body = {"email": NEW_EMAIL, "full_name": "X", "role": "viewer"} if method == "POST" else {"role": "viewer"}
    response = await client.request(method, path, json=body if method != "GET" else None, headers=csrf_headers(client))

    assert response.status_code == expected


# ------------------------------------------------------------- crear


async def test_admin_creates_user_with_temporary_password_that_must_be_changed(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    await _as_admin(app, client)

    response = await _create(client)

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["role"] == "operator" and body["user"]["must_change_password"] is True
    temporary = body["temporary_password"]
    assert len(temporary) >= 12

    # El usuario nuevo entra con la temporal y queda obligado a cambiarla (RF-06).
    newcomer = await login(httpx.AsyncClient(transport=client._transport, base_url="https://testserver"), NEW_EMAIL, temporary)
    assert newcomer.status_code == 200
    assert newcomer.json()["user"]["must_change_password"] is True
    assert "users.created" in await _audit_actions(app)


async def test_temporary_password_is_never_written_to_the_audit_log(app: FastAPI, client: httpx.AsyncClient) -> None:
    await _as_admin(app, client)
    temporary = (await _create(client)).json()["temporary_password"]

    async with app.state.session_factory() as session:
        details = list(await session.scalars(select(AuditLogModel.details)))

    assert temporary not in str(details)


async def test_duplicate_email_is_a_conflict(app: FastAPI, client: httpx.AsyncClient) -> None:
    await _as_admin(app, client)
    await _create(client)

    duplicated = await _create(client, email=NEW_EMAIL.upper())  # mismo correo en mayúsculas

    assert duplicated.status_code == 409


async def test_unknown_role_is_rejected(app: FastAPI, client: httpx.AsyncClient) -> None:
    await _as_admin(app, client)

    response = await _create(client, role="superusuario")

    assert response.status_code == 422
    assert "role" in response.json()["errors"]


# ------------------------------------------------------- listar y roles


async def test_list_is_paginated_and_searchable(app: FastAPI, client: httpx.AsyncClient) -> None:
    await _as_admin(app, client)
    for i in range(3):
        await create_user(app, f"op{i}@flota.example.com", role="operator")

    first = (await client.get("/api/v1/users", params={"page": 1, "page_size": 2})).json()
    search = (await client.get("/api/v1/users", params={"q": "OP1@"})).json()
    literal = (await client.get("/api/v1/users", params={"q": "%"})).json()  # "%" no es comodín

    assert (first["total"], first["page"], first["page_size"], len(first["items"])) == (4, 1, 2, 2)
    assert [u["email"] for u in search["items"]] == ["op1@flota.example.com"]
    assert literal["total"] == 0


async def test_roles_endpoint_lists_the_three_roles(app: FastAPI, client: httpx.AsyncClient) -> None:
    await _as_admin(app, client)

    roles = {r["name"]: r for r in (await client.get("/api/v1/roles")).json()}

    assert set(roles) == {"admin", "operator", "viewer"}
    assert "users:write" not in roles["operator"]["permissions"]


# ------------------------------------------- cambiar rol / desactivar


async def test_admin_changes_role_and_the_user_gets_new_permissions(app: FastAPI, client: httpx.AsyncClient) -> None:
    await _as_admin(app, client)
    user_id = (await _create(client, role="viewer")).json()["user"]["id"]

    response = await client.patch(f"/api/v1/users/{user_id}", json={"role": "operator"}, headers=csrf_headers(client))

    assert response.status_code == 200
    assert response.json()["role"] == "operator"
    assert "drivers:write" in response.json()["permissions"]
    async with app.state.session_factory() as session:
        details = await session.scalar(
            select(AuditLogModel.details).where(AuditLogModel.action == "users.updated")
        )
    assert details == {"role": {"from": "viewer", "to": "operator"}}  # el antes y el después


async def test_deactivated_user_loses_access_immediately(app: FastAPI, client: httpx.AsyncClient) -> None:
    await _as_admin(app, client)
    victim_id = await create_user(app, "baja@flota.example.com", role="operator")
    victim = httpx.AsyncClient(transport=client._transport, base_url="https://testserver")
    await login(victim, "baja@flota.example.com")
    assert (await victim.get("/api/v1/auth/me")).status_code == 200

    await client.patch(f"/api/v1/users/{victim_id}", json={"is_active": False}, headers=csrf_headers(client))

    assert (await victim.get("/api/v1/auth/me")).status_code == 401  # sin esperar a que expire el JWT
    assert (await login(victim, "baja@flota.example.com")).status_code == 401


async def test_admin_cannot_demote_or_deactivate_themselves(app: FastAPI, client: httpx.AsyncClient) -> None:
    admin_id = await _as_admin(app, client)

    demote = await client.patch(f"/api/v1/users/{admin_id}", json={"role": "viewer"}, headers=csrf_headers(client))
    disable = await client.patch(f"/api/v1/users/{admin_id}", json={"is_active": False}, headers=csrf_headers(client))

    assert demote.status_code == disable.status_code == 409


async def test_patch_without_changes_writes_nothing(app: FastAPI, client: httpx.AsyncClient) -> None:
    admin_id = await _as_admin(app, client)

    response = await client.patch(f"/api/v1/users/{admin_id}", json={}, headers=csrf_headers(client))

    assert response.status_code == 200
    assert "users.updated" not in await _audit_actions(app)


async def test_unknown_user_is_404(app: FastAPI, client: httpx.AsyncClient) -> None:
    await _as_admin(app, client)

    assert (await client.get("/api/v1/users/999")).status_code == 404


# --------------------------------------------- restablecer credenciales


async def test_reset_password_unlocks_and_forces_a_change(app: FastAPI, client: httpx.AsyncClient) -> None:
    await _as_admin(app, client)
    user_id = await create_user(app, "olvido@flota.example.com", role="viewer")
    other = httpx.AsyncClient(transport=client._transport, base_url="https://testserver")
    for _ in range(5):  # bloquea la cuenta por intentos fallidos
        await login(other, "olvido@flota.example.com", "Clave-Equivocada-1")

    response = await client.post(f"/api/v1/users/{user_id}/reset-password", headers=csrf_headers(client))

    assert response.status_code == 200
    temporary = response.json()["temporary_password"]
    relogin = await login(other, "olvido@flota.example.com", temporary)
    assert relogin.status_code == 200  # desbloqueada y con la nueva temporal
    assert relogin.json()["user"]["must_change_password"] is True
    assert "users.password_reset" in await _audit_actions(app)


async def test_writes_require_csrf(app: FastAPI, client: httpx.AsyncClient) -> None:
    await _as_admin(app, client)

    response = await client.post("/api/v1/users", json={"email": NEW_EMAIL, "full_name": "X", "role": "viewer"})

    assert response.status_code == 403
