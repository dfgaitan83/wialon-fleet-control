"""Registro de auditoría (RF-26): solo el Admin lo ve; filtra por categoría; recientes primero."""

import httpx
import pytest
from fastapi import FastAPI

from tests.conftest import ADMIN_EMAIL, create_user, login


async def test_admin_sees_failed_logins_newest_first(app: FastAPI, client: httpx.AsyncClient) -> None:
    await create_user(app, ADMIN_EMAIL)
    await login(client, "nadie@flota.example.com", "Clave-Mala-12345")  # login fallido auditado
    await login(client, ADMIN_EMAIL)

    body = (await client.get("/api/v1/audit", params={"category": "auth"})).json()

    actions = [item["action"] for item in body["items"]]
    assert actions[0] == "auth.login_succeeded"  # el más reciente primero
    assert "auth.login_failed" in actions
    assert all(a.startswith("auth.") for a in actions)


@pytest.mark.parametrize("role", ["operator", "viewer"])
async def test_only_admin_can_read_the_audit_log(app: FastAPI, client: httpx.AsyncClient, role: str) -> None:
    await create_user(app, f"{role}@flota.example.com", role=role)
    await login(client, f"{role}@flota.example.com")

    assert (await client.get("/api/v1/audit")).status_code == 403
