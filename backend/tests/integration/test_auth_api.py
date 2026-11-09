"""Tests de integración de /api/v1/auth (RF-04, RF-06, SEG-01, SEG-07, SEG-11).

App real + BD SQLite migrada con Alembic + cliente HTTP. Sin Wialon.
"""

from typing import Annotated

import httpx
import pytest
from fastapi import Depends, FastAPI
from sqlalchemy import func, select

from app.api.deps import require_permission
from app.domain.permissions import Permission
from app.domain.users import User
from app.infrastructure.db.models import AuditLogModel
from tests.conftest import (
    ADMIN_EMAIL,
    STRONG_PASSWORD,
    create_user,
    csrf_headers,
    login,
    make_settings,
)

PROBLEM_JSON = "application/problem+json"


async def _audit_count(app: FastAPI, action: str) -> int:
    async with app.state.session_factory() as session:
        return await session.scalar(select(func.count()).where(AuditLogModel.action == action)) or 0


def _set_cookie(response: httpx.Response, name: str) -> str:
    return next(h for h in response.headers.get_list("set-cookie") if h.startswith(f"{name}="))


# ------------------------------------------------------------------ login / me


async def test_login_sets_hardened_cookies_and_returns_permissions(app: FastAPI, client: httpx.AsyncClient) -> None:
    await create_user(app, ADMIN_EMAIL)

    response = await login(client, ADMIN_EMAIL)

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == ADMIN_EMAIL
    assert body["user"]["role"] == "admin"
    assert set(body["user"]["permissions"]) == {str(p) for p in Permission}  # Admin: todos
    assert "access_token" not in body and "refresh_token" not in body  # los tokens solo en cookies

    access = _set_cookie(response, "fleet_access").lower()
    refresh = _set_cookie(response, "fleet_refresh").lower()
    csrf = _set_cookie(response, "fleet_csrf").lower()
    assert all(attr in access for attr in ("httponly", "secure", "samesite=lax", "path=/api"))
    assert all(attr in refresh for attr in ("httponly", "secure", "samesite=strict", "path=/api/v1/auth"))
    assert "httponly" not in csrf and "secure" in csrf  # el JS debe poder leer la cookie CSRF


async def test_me_returns_the_session_user(app: FastAPI, client: httpx.AsyncClient) -> None:
    await create_user(app, ADMIN_EMAIL)
    await login(client, ADMIN_EMAIL)

    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == ADMIN_EMAIL


async def test_without_cookie_me_is_401_problem_details(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.headers["content-type"].startswith(PROBLEM_JSON)
    assert response.json()["type"] == "/problems/invalid-session"


async def test_forged_access_cookie_is_rejected(client: httpx.AsyncClient) -> None:
    client.cookies.set("fleet_access", "eyJhbGciOiJub25lIn0.eyJzdWIiOiIxIn0.", path="/api")  # alg=none

    assert (await client.get("/api/v1/auth/me")).status_code == 401


# ------------------------------------------------------- enumeración y bloqueo


async def test_wrong_password_and_unknown_email_get_identical_answers(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    await create_user(app, ADMIN_EMAIL)

    wrong_password = await login(client, ADMIN_EMAIL, "Otra-Clave-12345")
    unknown_email = await login(client, "nadie@flota.example.com", "Otra-Clave-12345")

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json()["detail"] == unknown_email.json()["detail"]  # SEG-07: no revela si existe
    assert await _audit_count(app, "auth.login_failed") == 2  # ambos quedan auditados (RF-26)


async def test_account_locks_after_max_failed_attempts(app: FastAPI, client: httpx.AsyncClient) -> None:
    await create_user(app, ADMIN_EMAIL)
    for _ in range(5):  # login_max_attempts por defecto
        await login(client, ADMIN_EMAIL, "Clave-Incorrecta-1")

    # Ni siquiera la contraseña CORRECTA entra mientras dura el bloqueo.
    response = await login(client, ADMIN_EMAIL)

    assert response.status_code == 401
    assert await _audit_count(app, "auth.account_locked") == 1


async def test_inactive_user_cannot_log_in(app: FastAPI, client: httpx.AsyncClient) -> None:
    await create_user(app, "baja@flota.example.com", is_active=False)

    assert (await login(client, "baja@flota.example.com")).status_code == 401


async def test_login_is_rate_limited_per_ip(database_url: str) -> None:
    from app.main import create_app

    limited = create_app(make_settings(database_url, login_rate_limit="3/minute"))
    transport = httpx.ASGITransport(app=limited)
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as http:
        codes = [(await login(http, "x@flota.example.com", "Clave-1234567")).status_code for _ in range(4)]

    assert codes == [401, 401, 401, 429]


async def test_invalid_payload_returns_field_errors(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/auth/login", json={"email": "no-es-correo", "password": "x"})

    assert response.status_code == 422
    assert "email" in response.json()["errors"]


# --------------------------------------------------------- refresh rotatorio


async def test_refresh_rotates_and_detects_reuse(app: FastAPI, client: httpx.AsyncClient) -> None:
    await create_user(app, ADMIN_EMAIL)
    await login(client, ADMIN_EMAIL)
    stolen = client.cookies.get("fleet_refresh")

    rotated = await client.post("/api/v1/auth/refresh", headers=csrf_headers(client))
    assert rotated.status_code == 200
    assert client.cookies.get("fleet_refresh") != stolen  # rotación: token nuevo

    # Un atacante reutiliza el token VIEJO -> se revoca toda la sesión.
    client.cookies.set("fleet_refresh", stolen, path="/api/v1/auth")
    reused = await client.post("/api/v1/auth/refresh", headers=csrf_headers(client))
    assert reused.status_code == 401
    assert await _audit_count(app, "auth.refresh_reuse_detected") == 1


async def test_refresh_without_cookie_is_401(client: httpx.AsyncClient) -> None:
    client.cookies.set("fleet_csrf", "abc")
    response = await client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": "abc"})

    assert response.status_code == 401


# --------------------------------------------------------------- CSRF y logout


async def test_state_changing_requests_require_csrf(app: FastAPI, client: httpx.AsyncClient) -> None:
    await create_user(app, ADMIN_EMAIL)
    await login(client, ADMIN_EMAIL)

    without = await client.post("/api/v1/auth/logout")
    mismatched = await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "otro-valor"})

    assert without.status_code == mismatched.status_code == 403


async def test_logout_invalidates_the_session_on_the_server(app: FastAPI, client: httpx.AsyncClient) -> None:
    await create_user(app, ADMIN_EMAIL)
    await login(client, ADMIN_EMAIL)
    refresh_token = client.cookies.get("fleet_refresh")
    headers = csrf_headers(client)

    assert (await client.post("/api/v1/auth/logout", headers=headers)).status_code == 204

    # Aunque alguien guardara el refresh token, ya no sirve.
    client.cookies.set("fleet_refresh", refresh_token, path="/api/v1/auth")
    client.cookies.set("fleet_csrf", headers["X-CSRF-Token"])
    assert (await client.post("/api/v1/auth/refresh", headers=headers)).status_code == 401


# ------------------------------------------------- permisos (require_permission)


UsersReader = Annotated[User, Depends(require_permission(Permission.USERS_READ))]


def _add_protected_route(app: FastAPI) -> None:
    @app.get("/api/v1/_test/users")
    async def protected(user: UsersReader) -> dict[str, str]:
        return {"email": user.email}


@pytest.mark.parametrize(
    ("role", "expected"),
    [("admin", 200), ("operator", 403), ("viewer", 403)],
)
async def test_require_permission_applies_the_role_matrix(
    app: FastAPI, client: httpx.AsyncClient, role: str, expected: int
) -> None:
    _add_protected_route(app)
    await create_user(app, f"{role}@flota.example.com", role=role)
    await login(client, f"{role}@flota.example.com")

    assert (await client.get("/api/v1/_test/users")).status_code == expected


async def test_denied_access_is_audited(app: FastAPI, client: httpx.AsyncClient) -> None:
    _add_protected_route(app)
    await create_user(app, "viewer@flota.example.com", role="viewer")
    await login(client, "viewer@flota.example.com")

    await client.get("/api/v1/_test/users")

    assert await _audit_count(app, "auth.access_denied") == 1


async def test_protected_route_without_session_is_401(app: FastAPI, client: httpx.AsyncClient) -> None:
    _add_protected_route(app)

    assert (await client.get("/api/v1/_test/users")).status_code == 401


# ------------------------------------------------------ cambio de contraseña


async def test_user_must_change_password_before_using_the_platform(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    _add_protected_route(app)
    await create_user(app, ADMIN_EMAIL, must_change_password=True)
    session = await login(client, ADMIN_EMAIL)
    assert session.json()["user"]["must_change_password"] is True

    blocked = await client.get("/api/v1/_test/users")
    assert blocked.status_code == 403
    assert blocked.json()["type"] == "/problems/password-change-required"

    changed = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": STRONG_PASSWORD, "new_password": "Nueva-Clave-Segura-99"},
        headers=csrf_headers(client),
    )
    assert changed.status_code == 200
    assert changed.json()["user"]["must_change_password"] is False
    assert (await client.get("/api/v1/_test/users")).status_code == 200
    # La contraseña vieja deja de funcionar.
    assert (await login(client, ADMIN_EMAIL)).status_code == 401


@pytest.mark.parametrize(
    ("current", "new", "field"),
    [
        ("Clave-Equivocada-1", "Nueva-Clave-Segura-99", "current_password"),
        (STRONG_PASSWORD, "corta1", "new_password"),
        (STRONG_PASSWORD, "solo-letras-sin-numeros", "new_password"),
        (STRONG_PASSWORD, STRONG_PASSWORD, "new_password"),
    ],
)
async def test_change_password_validates_input(
    app: FastAPI, client: httpx.AsyncClient, current: str, new: str, field: str
) -> None:
    await create_user(app, ADMIN_EMAIL)
    await login(client, ADMIN_EMAIL)

    response = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": current, "new_password": new},
        headers=csrf_headers(client),
    )

    assert response.status_code == 422
    assert field in response.json()["errors"]


# ------------------------------------------------ cabeceras y errores (SEG-05/10)


async def test_security_headers_are_present(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    headers = response.headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["cache-control"] == "no-store"
    assert "default-src 'none'" in headers["content-security-policy"]
    assert headers["x-request-id"]


async def test_unexpected_errors_never_leak_internals(app: FastAPI, client: httpx.AsyncClient) -> None:
    @app.get("/api/v1/_test/boom")
    async def boom() -> None:
        raise RuntimeError("detalle interno secreto: tabla users")

    response = await client.get("/api/v1/_test/boom")

    assert response.status_code == 500
    assert "secreto" not in response.text and "Traceback" not in response.text
    assert response.json()["title"] == "Error interno del servidor"
