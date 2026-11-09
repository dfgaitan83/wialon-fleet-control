"""Tests unitarios del cliente Wialon (M1, TST-01). No llaman a Wialon real.

Técnica: **respx** intercepta httpx. Cada test recibe el fixture ``respx_mock``
(plugin de respx) y registra una función ``handler`` que recibe cada petición y
devuelve una respuesta simulada. El cliente se construye IGUAL que en producción
(sin inyectarle un http_client), así se prueba también su configuración real.
Red de seguridad: respx hace FALLAR el test ante cualquier petición no simulada,
de modo que ningún test puede llegar a Wialon real por accidente.

Las tres pruebas exigidas por el plan M1:
- Login correcto ............. ``test_login_search_and_logout_flow``
- Re-login transparente (1) .. ``test_expired_session_relogins_once_and_retries``
- Timeout -> WialonUnavailable ``test_timeout_raises_wialon_unavailable``

Ejecutar (desde backend/):
    uv run pytest -q
"""

# asyncio: lanzar peticiones concurrentes (test del lock).
# parse_qs: decodifica el cuerpo form-urlencoded que envía el cliente.
import asyncio
import json
from urllib.parse import parse_qs

import httpx
import pytest
import respx

from app.infrastructure.wialon.client import (
    NETWORK_MAX_ATTEMPTS,
    SENSITIVE_LOGIN_KEYS,
    UNIT_FLAGS_EXPLORE,
    WialonClient,
)
from app.infrastructure.wialon.errors import (
    WialonAccessDenied,
    WialonNotFound,
    WialonSessionError,
    WialonUnavailable,
)
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


def _make_client(router: respx.MockRouter, handler) -> WialonClient:
    """Crea un WialonClient real cuya red simula respx con la función ``handler``."""
    router.post(BASE_URL).mock(side_effect=handler)  # todo POST a ajax.html pasa por handler
    # network_retry_wait=0: los reintentos de red no esperan (tests rápidos y deterministas).
    return WialonClient(BASE_URL, "fake-token", network_retry_wait=0)


def _form(request: httpx.Request) -> dict[str, str]:
    """Convierte el cuerpo 'svc=...&params=...&sid=...' en dict para inspeccionarlo."""
    return {k: v[0] for k, v in parse_qs(request.content.decode()).items()}


async def test_login_search_and_logout_flow(respx_mock: respx.MockRouter) -> None:
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
    async with _make_client(respx_mock, handler) as client:
        assert client.session.user_name == "demo"
        units = await client.search_items("avl_unit", UNIT_FLAGS_EXPLORE)

    # Assert: datos correctos y el "async with" hizo logout al salir.
    assert units == [{"id": 1, "nm": "Bus 1"}]
    assert calls == ["token/login", "core/search_items", "core/logout"]


async def test_login_raw_never_contains_secrets(respx_mock: respx.MockRouter) -> None:
    """Seguridad: el token en claro (th), sid, gis_sid e IP NO quedan en session.raw."""
    client = _make_client(respx_mock,lambda _req: httpx.Response(200, json=LOGIN_OK))
    session = await client.ensure_session()
    assert SENSITIVE_LOGIN_KEYS.isdisjoint(session.raw)  # ninguna clave sensible presente
    assert "token-en-claro" not in json.dumps(session.raw)  # ni siquiera anidada
    await client.close()


async def test_concurrent_calls_login_only_once(respx_mock: respx.MockRouter) -> None:
    """Concurrencia: 10 peticiones simultáneas sin sesión -> UN solo login (asyncio.Lock)."""
    logins = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal logins
        if _form(request)["svc"] == "token/login":
            logins += 1
            await asyncio.sleep(0.01)  # login "lento": da tiempo a que las demás choquen
            return httpx.Response(200, json=LOGIN_OK)
        return httpx.Response(200, json={"items": []})

    client = _make_client(respx_mock,handler)
    # gather lanza las 10 a la vez; sin el lock, cada una haría su propio login.
    await asyncio.gather(*(client.search_items("avl_unit", 1) for _ in range(10)))
    await client.close()
    assert logins == 1


async def test_expired_session_relogins_once_and_retries(respx_mock: respx.MockRouter) -> None:
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

    client = _make_client(respx_mock,handler)
    await client.ensure_session()  # primer login -> sid-1
    units = await client.search_items("avl_unit", 1)  # falla con sid-1, re-login, reintenta
    assert units == [{"id": 9}]
    assert client.session.sid == "sid-2"  # se usa la sesión nueva
    assert state["logins"] == 2  # exactamente un re-login
    await client.close()


async def test_invalid_token_raises_session_error(respx_mock: respx.MockRouter) -> None:
    """Token inválido (error 8): WialonSessionError con el código original."""
    client = _make_client(respx_mock,lambda _req: httpx.Response(200, json={"error": 8}))
    with pytest.raises(WialonSessionError) as exc_info:
        await client.ensure_session()
    await client.close()
    assert exc_info.value.code == 8


async def test_network_failure_raises_unavailable(respx_mock: respx.MockRouter) -> None:
    """Sin red: httpx.ConnectError -> WialonUnavailable(-1), no explota la app."""

    def handler(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin red")

    client = _make_client(respx_mock,handler)
    with pytest.raises(WialonUnavailable) as exc_info:
        await client.ensure_session()
    await client.close()
    assert exc_info.value.code == -1


async def test_transient_connect_error_is_retried_until_success(respx_mock: respx.MockRouter) -> None:
    """tenacity: 2 fallos de conexión y luego éxito -> la llamada funciona (3 intentos)."""
    attempts = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise httpx.ConnectError("conexión rechazada")
        return httpx.Response(200, json=LOGIN_OK)

    client = _make_client(respx_mock,handler)
    session = await client.ensure_session()
    await client.close()
    assert session.sid == "sid-1"
    assert attempts >= 3  # 3 del login (+1 del logout al cerrar)


async def test_persistent_connect_error_gives_up_after_max_attempts(respx_mock: respx.MockRouter) -> None:
    """Sin red de forma persistente: se rinde tras NETWORK_MAX_ATTEMPTS y lanza WialonUnavailable."""
    attempts = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("sin red")

    client = _make_client(respx_mock,handler)
    with pytest.raises(WialonUnavailable):
        await client.ensure_session()
    assert attempts == NETWORK_MAX_ATTEMPTS == 3
    await client.close()


def test_client_uses_a_ten_second_timeout() -> None:
    """El timeout de 10 s del plan llega de verdad al cliente HTTP (conectar, enviar y leer)."""
    client = WialonClient(BASE_URL, "fake-token")

    assert client._http.timeout == httpx.Timeout(10.0)


@pytest.mark.parametrize(
    ("timeout", "expected_attempts"),
    [
        # ReadTimeout: la petición YA se envió (Wialon pudo procesarla) -> no se reintenta.
        (httpx.ReadTimeout("Wialon tardó más de 10 s en responder"), 1),
        # ConnectTimeout: la conexión ni se abrió (nada llegó a Wialon) -> tenacity reintenta.
        (httpx.ConnectTimeout("no se pudo conectar en 10 s"), NETWORK_MAX_ATTEMPTS),
    ],
)
async def test_timeout_raises_wialon_unavailable(
    respx_mock: respx.MockRouter, timeout: Exception, expected_attempts: int
) -> None:
    """Plan M1: un timeout se traduce a WialonUnavailable (-> 503), nunca cuelga ni explota."""
    attempts = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise timeout

    client = _make_client(respx_mock, handler)
    with pytest.raises(WialonUnavailable) as exc_info:
        await client.ensure_session()
    await client.close()
    assert exc_info.value.code == -1
    assert attempts == expected_attempts


async def test_dropped_connection_after_sending_is_not_retried(
    respx_mock: respx.MockRouter,
) -> None:
    """La petición PUDO llegar a Wialon: reintentar duplicaría una escritura -> 1 solo intento."""
    attempts = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.RemoteProtocolError("el servidor cortó la conexión")

    client = _make_client(respx_mock,handler)
    with pytest.raises(WialonUnavailable):
        await client.ensure_session()
    assert attempts == 1
    await client.close()


async def test_http_5xx_is_unavailable_and_not_retried(respx_mock: respx.MockRouter) -> None:
    """HTTP 503 no es un error de red (el servidor respondió): WialonUnavailable sin reintento."""
    attempts = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503)

    client = _make_client(respx_mock,handler)
    with pytest.raises(WialonUnavailable):
        await client.ensure_session()
    assert attempts == 1
    await client.close()


async def test_non_json_response_raises_unavailable(respx_mock: respx.MockRouter) -> None:
    """Un proxy devuelve una página HTML (no JSON): WialonUnavailable, no un ValueError."""
    client = _make_client(respx_mock,lambda _req: httpx.Response(200, text="<html>502</html>"))
    with pytest.raises(WialonUnavailable):
        await client.ensure_session()
    await client.close()


async def test_search_item_returns_the_item(respx_mock: respx.MockRouter) -> None:
    """``search_item`` pide UN elemento por id y devuelve solo su bloque ``item``."""

    def handler(request: httpx.Request) -> httpx.Response:
        form = _form(request)
        if form["svc"] == "token/login":
            return httpx.Response(200, json=LOGIN_OK)
        if form["svc"] == "core/search_item":
            assert json.loads(form["params"]) == {"id": 42, "flags": 1}
            return httpx.Response(200, json={"item": {"id": 42, "nm": "Bus 42"}, "flags": 1})
        return httpx.Response(200, json={"error": 0})  # logout ok

    client = _make_client(respx_mock,handler)
    item = await client.search_item(42, 1)
    await client.close()
    assert item == {"id": 42, "nm": "Bus 42"}


async def test_search_item_unknown_id_raises_not_found(respx_mock: respx.MockRouter) -> None:
    """Wialon responde 7 a un id inexistente (verificado): el cliente lo expone como 404."""

    def handler(request: httpx.Request) -> httpx.Response:
        if _form(request)["svc"] == "token/login":
            return httpx.Response(200, json=LOGIN_OK)
        return httpx.Response(200, json={"error": 7})

    client = _make_client(respx_mock,handler)
    with pytest.raises(WialonNotFound) as exc_info:
        await client.search_item(999_999_999, 1)
    await client.close()
    assert exc_info.value.code == 7  # se conserva el código original de Wialon


async def test_access_denied_outside_search_item_stays_access_denied(respx_mock: respx.MockRouter) -> None:
    """Fuera de la búsqueda por id (ej. una escritura), el 7 sigue siendo 403."""

    def handler(request: httpx.Request) -> httpx.Response:
        if _form(request)["svc"] == "token/login":
            return httpx.Response(200, json=LOGIN_OK)
        return httpx.Response(200, json={"error": 7})

    client = _make_client(respx_mock,handler)
    with pytest.raises(WialonAccessDenied):
        await client.call("item/update_name", {"itemId": 1, "name": "x"})
    await client.close()


def test_redact_resources_masks_passwords_without_mutating() -> None:
    """Fixtures: las contraseñas del jp se enmascaran y el objeto original NO se modifica."""
    # Valores ficticios a propósito: nunca copiar datos reales de la cuenta compartida a los tests.
    jp = {"Password": "falso-1", "ID": "0000000099", "Route": "Ruta A"}
    original = [{"id": 1, "tags": {"5": {"id": 5, "n": "Ana", "jp": jp}}}]
    redacted = redact_resources(original)
    # Secreto -> "***"; documento -> enmascarado parcial; dato no sensible -> intacto.
    assert redacted[0]["tags"]["5"]["jp"] == {"Password": "***", "ID": "********99", "Route": "Ruta A"}
    assert original[0]["tags"]["5"]["jp"]["Password"] == "falso-1"  # inmutabilidad
