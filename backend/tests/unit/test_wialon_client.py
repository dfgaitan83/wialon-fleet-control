"""Tests unitarios del cliente Wialon (M1). No llaman a Wialon real.

Técnica: ``httpx.MockTransport`` reemplaza la red por una función ``handler`` que
recibe cada petición y devuelve una respuesta simulada. Se inyecta en el cliente
por el parámetro ``http_client`` (inyección de dependencias).

Ejecutar (desde backend/):
    python -m uv run pytest -q
"""

# asyncio: lanzar peticiones concurrentes (test del lock).
# parse_qs: decodifica el cuerpo form-urlencoded que envía el cliente.
import asyncio
import json
from urllib.parse import parse_qs

import httpx
import pytest

from app.infrastructure.wialon.client import (
    SENSITIVE_LOGIN_KEYS,
    UNIT_FLAGS_EXPLORE,
    WialonClient,
)
from app.infrastructure.wialon.errors import WialonError
from scripts.wialon_explorer import redact_resources

# Dominio falso (.test no existe): si algo intentara salir a la red, fallaría.
BASE_URL = "https://wialon.test/wialon/ajax.html"
# Respuesta de login simulada con la MISMA forma que la real, incluidos los campos sensibles.
LOGIN_OK = {
    "eid": "sid-1",
    "th": "token-en-claro",
    "gis_sid": "gis",
    "host": "1.2.3.4",
    "tm": 1,
    "user": {"nm": "demo", "id": 7},
}


def _make_client(handler) -> WialonClient:
    """Crea un WialonClient cuya red es la función ``handler`` (sin internet)."""
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return WialonClient(BASE_URL, "fake-token", http_client=http)


def _form(request: httpx.Request) -> dict[str, str]:
    """Convierte el cuerpo 'svc=...&params=...&sid=...' en dict para inspeccionarlo."""
    return {k: v[0] for k, v in parse_qs(request.content.decode()).items()}


async def test_login_search_and_logout_flow() -> None:
    """Flujo completo: login -> search_items -> logout, en ese orden y con el sid correcto."""
    # Arrange: el handler responde según el servicio y registra el orden de llamadas.
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        form = _form(request)
        calls.append(form["svc"])
        if form["svc"] == "token/login":
            assert json.loads(form["params"]) == {"token": "fake-token"}  # se envía el token
            return httpx.Response(200, json=LOGIN_OK)
        assert form["sid"] == "sid-1"  # el resto de llamadas usan el sid del login
        if form["svc"] == "core/search_items":
            # Los flags viajan en DECIMAL: 1 + 8 + 256 + 1024 + 4096 = 5385.
            assert json.loads(form["params"])["flags"] == UNIT_FLAGS_EXPLORE == 5385
            return httpx.Response(200, json={"items": [{"id": 1, "nm": "Bus 1"}]})
        return httpx.Response(200, json={"error": 0})  # logout ok

    # Act
    async with _make_client(handler) as client:
        assert client.session.user_name == "demo"
        units = await client.search_items("avl_unit", UNIT_FLAGS_EXPLORE)

    # Assert: datos correctos y el "async with" hizo logout al salir.
    assert units == [{"id": 1, "nm": "Bus 1"}]
    assert calls == ["token/login", "core/search_items", "core/logout"]


async def test_login_raw_never_contains_secrets() -> None:
    """Seguridad: el token en claro (th), sid, gis_sid e IP NO quedan en session.raw."""
    client = _make_client(lambda _req: httpx.Response(200, json=LOGIN_OK))
    session = await client.ensure_session()
    assert SENSITIVE_LOGIN_KEYS.isdisjoint(session.raw)  # ninguna clave sensible presente
    assert "token-en-claro" not in json.dumps(session.raw)  # ni siquiera anidada
    await client.close()


async def test_concurrent_calls_login_only_once() -> None:
    """Concurrencia: 10 peticiones simultáneas sin sesión -> UN solo login (asyncio.Lock)."""
    logins = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal logins
        if _form(request)["svc"] == "token/login":
            logins += 1
            await asyncio.sleep(0.01)  # login "lento": da tiempo a que las demás choquen
            return httpx.Response(200, json=LOGIN_OK)
        return httpx.Response(200, json={"items": []})

    client = _make_client(handler)
    # gather lanza las 10 a la vez; sin el lock, cada una haría su propio login.
    await asyncio.gather(*(client.search_items("avl_unit", 1) for _ in range(10)))
    await client.close()
    assert logins == 1


async def test_expired_session_relogins_once_and_retries() -> None:
    """Sesión expirada (error 1): renueva sesión, reintenta UNA vez y devuelve los datos."""
    state = {"logins": 0, "expired_sent": False}

    def handler(request: httpx.Request) -> httpx.Response:
        form = _form(request)
        if form["svc"] == "token/login":
            state["logins"] += 1
            # Cada login devuelve un sid distinto: sid-1, sid-2...
            return httpx.Response(200, json={**LOGIN_OK, "eid": f"sid-{state['logins']}"})
        if form["sid"] == "sid-1" and not state["expired_sent"]:
            state["expired_sent"] = True
            return httpx.Response(200, json={"error": 1})  # simula que la sesión caducó
        return httpx.Response(200, json={"items": [{"id": 9}]})

    client = _make_client(handler)
    await client.ensure_session()  # primer login -> sid-1
    units = await client.search_items("avl_unit", 1)  # falla con sid-1, re-login, reintenta
    assert units == [{"id": 9}]
    assert client.session.sid == "sid-2"  # se usa la sesión nueva
    assert state["logins"] == 2  # exactamente un re-login
    await client.close()


async def test_invalid_token_raises_wialon_error() -> None:
    """Token inválido (error 8): se convierte en WialonError con el código original."""
    client = _make_client(lambda _req: httpx.Response(200, json={"error": 8}))
    with pytest.raises(WialonError) as exc_info:
        await client.ensure_session()
    await client.close()
    assert exc_info.value.code == 8


async def test_network_failure_is_wrapped() -> None:
    """Sin red: httpx.ConnectError se envuelve en WialonError(-1), no explota la app."""

    def handler(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin red")

    client = _make_client(handler)
    with pytest.raises(WialonError) as exc_info:
        await client.ensure_session()
    await client.close()
    assert exc_info.value.code == -1


def test_redact_resources_masks_passwords_without_mutating() -> None:
    """Fixtures: las contraseñas del jp se enmascaran y el objeto original NO se modifica."""
    # Valor ficticio a propósito: nunca copiar datos reales de la cuenta compartida a los tests.
    original = [{"id": 1, "tags": {"5": {"n": "Ana", "jp": {"Password": "falso-1", "ID": "1"}}}}]
    redacted = redact_resources(original)
    assert redacted[0]["tags"]["5"]["jp"] == {"Password": "***", "ID": "1"}  # solo el sensible
    assert original[0]["tags"]["5"]["jp"]["Password"] == "falso-1"  # inmutabilidad
