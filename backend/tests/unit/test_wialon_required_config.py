"""Guardia de requisito: la app DEBE usar la base URL de Wialon que exige el reclutador.

¿Por qué existe? La prueba técnica obliga a conectarse a
``https://hst-api.wialon.com/wialon/ajax.html`` con el token entregado; usar otra
base descalifica. Este test falla en la CI si alguien cambia la URL por error
(en el código o en la plantilla ``.env.example``), ANTES de que llegue a GitHub.

El token real NO puede comprobarse aquí: vive solo en ``backend/.env`` (ignorado
por git). Lo que sí se vigila es lo contrario: que la plantilla pública
``.env.example`` nunca contenga un token real pegado por accidente.
"""

import inspect
import re
from pathlib import Path

from app.core.config import Settings
from app.infrastructure.wialon.client import WialonClient

# Valor EXACTO exigido por el enunciado. Escrito aquí a propósito (y no importado de
# config.py): si se importara, un cambio en config.py cambiaría también la expectativa
# y el test nunca fallaría.
REQUIRED_WIALON_BASE_URL = "https://hst-api.wialon.com/wialon/ajax.html"
# Plan M1: "timeout de 10 s" por petición a Wialon. Literal por la misma razón.
REQUIRED_WIALON_TIMEOUT_SECONDS = 10.0

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"
# Formato de un token de Wialon: 72 caracteres hexadecimales.
REAL_TOKEN_PATTERN = re.compile(r"^[0-9a-fA-F]{72}$")


def _env_example_values() -> dict[str, str]:
    """Lee ``.env.example`` como CLAVE=valor, ignorando comentarios y líneas vacías."""
    values: dict[str, str] = {}
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip().strip("\"'")
    return values


def test_default_base_url_is_the_required_one() -> None:
    # Se lee el valor por defecto del campo sin instanciar Settings: así no depende
    # de que exista backend/.env ni de variables de entorno (en la CI no hay token real).
    default = Settings.model_fields["wialon_base_url"].default

    assert default == REQUIRED_WIALON_BASE_URL


def test_default_timeout_is_the_required_one() -> None:
    # Se vigilan los DOS valores por defecto: el de Settings (lo que usa la app) y el
    # del constructor del cliente (lo que usaría un script que no pase el parámetro).
    settings_default = Settings.model_fields["wialon_timeout_seconds"].default
    client_default = inspect.signature(WialonClient).parameters["timeout_seconds"].default

    assert settings_default == REQUIRED_WIALON_TIMEOUT_SECONDS
    assert client_default == REQUIRED_WIALON_TIMEOUT_SECONDS


def test_env_example_uses_the_required_timeout() -> None:
    # El .env tiene PRIORIDAD sobre el valor por defecto: si la plantilla dijera 15,
    # quien la copie usaría 15 s aunque el código diga 10.
    timeout = _env_example_values().get("WIALON_TIMEOUT_SECONDS")

    assert timeout is not None and float(timeout) == REQUIRED_WIALON_TIMEOUT_SECONDS


def test_env_example_points_to_the_required_base_url() -> None:
    # Quien clone el repo (el reclutador) copia .env.example -> .env: debe quedar bien.
    assert _env_example_values().get("WIALON_BASE_URL") == REQUIRED_WIALON_BASE_URL


def test_env_example_declares_the_token_variable() -> None:
    # Sin esta clave, quien clone el repo no sabría dónde poner el token entregado.
    assert "WIALON_TOKEN" in _env_example_values()


def test_env_example_never_contains_a_real_token() -> None:
    # El repo es público: un token real en la plantilla quedaría expuesto a todos.
    token = _env_example_values().get("WIALON_TOKEN", "")

    assert not REAL_TOKEN_PATTERN.match(token), "¡.env.example contiene un token real!"
