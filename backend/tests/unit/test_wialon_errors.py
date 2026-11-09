"""Tests de la jerarquía de errores de Wialon (``errors.py``). Sin red.

¿Por qué subclases? Cada capa superior necesita reaccionar distinto:
- ``WialonUnavailable`` -> HTTP 503 "intenta más tarde" (y la app no se cae).
- ``WialonAccessDenied`` -> HTTP 403.
- ``WialonNotFound`` -> HTTP 404.
- ``WialonSessionError`` -> problema de credenciales del backend con Wialon.
Con un solo ``WialonError`` el gateway tendría que comparar códigos numéricos
en todas partes; con subclases basta un ``except`` por tipo.
"""

import pytest

from app.infrastructure.wialon.errors import (
    ERROR_NETWORK,
    WialonAccessDenied,
    WialonError,
    WialonNotFound,
    WialonSessionError,
    WialonUnavailable,
    error_from_code,
)


@pytest.mark.parametrize(
    ("code", "expected_type"),
    [
        (1, WialonSessionError),  # sesión inválida o expirada
        (8, WialonSessionError),  # token inválido o expirado
        (1011, WialonSessionError),  # la IP cambió o la sesión expiró
        (7, WialonAccessDenied),  # acceso denegado (también si el id no existe: verificado)
        (ERROR_NETWORK, WialonUnavailable),  # fallo de red / timeout / HTTP 5xx
        (9, WialonUnavailable),  # servidor de autorización no disponible
        (10, WialonUnavailable),  # límite de peticiones concurrentes
        (1003, WialonUnavailable),  # solo una petición a la vez
    ],
)
def test_known_codes_map_to_their_subclass(code: int, expected_type: type[WialonError]) -> None:
    error = error_from_code(code, "detalle")

    assert type(error) is expected_type
    assert error.code == code  # el código original se conserva para logs y decisiones


@pytest.mark.parametrize("code", [2, 4, 5, 6, 123456])
def test_unmapped_codes_fall_back_to_base_error(code: int) -> None:
    error = error_from_code(code, "detalle")

    assert type(error) is WialonError


@pytest.mark.parametrize(
    "subclass", [WialonSessionError, WialonAccessDenied, WialonNotFound, WialonUnavailable]
)
def test_every_subclass_is_still_a_wialon_error(subclass: type[WialonError]) -> None:
    # Liskov: el código que ya captura WialonError (scripts, close()) sigue funcionando.
    assert issubclass(subclass, WialonError)


def test_error_message_is_readable_and_keeps_code() -> None:
    error = error_from_code(7, "Acceso denegado")

    assert str(error) == "Wialon error 7: Acceso denegado"
    assert error.message == "Acceso denegado"
