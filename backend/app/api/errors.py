"""Traducción de errores de la aplicación a Problem Details (único lugar con la tabla).

Abierto/cerrado: un error nuevo de la aplicación es UNA fila en ``_STATUS_BY_ERROR``.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.application.errors import (
    AppError,
    Conflict,
    InvalidCredentials,
    InvalidSession,
    NotFound,
    PasswordChangeRequired,
    PermissionDenied,
    ProviderUnavailable,
    ValidationFailed,
)
from app.core.errors import problem_response

# (código HTTP, slug del "type") por clase de error. Se recorre en orden: subclases primero.
_STATUS_BY_ERROR: tuple[tuple[type[AppError], int, str], ...] = (
    (InvalidCredentials, 401, "invalid-credentials"),
    (InvalidSession, 401, "invalid-session"),
    (PasswordChangeRequired, 403, "password-change-required"),
    (PermissionDenied, 403, "forbidden"),
    (NotFound, 404, "not-found"),
    (Conflict, 409, "conflict"),
    (ValidationFailed, 422, "validation"),
    (ProviderUnavailable, 503, "provider-unavailable"),
)


def _status_for(exc: AppError) -> tuple[int, str]:
    for error_type, status, slug in _STATUS_BY_ERROR:
        if isinstance(exc, error_type):
            return status, slug
    return 400, "bad-request"


async def _app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    status, slug = _status_for(exc)
    errors = exc.errors if isinstance(exc, ValidationFailed) else None
    return problem_response(request, status, exc.detail, slug=slug, errors=errors)


async def _rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
    return problem_response(
        request,
        429,
        "Demasiados intentos desde tu conexión. Espera un minuto e inténtalo de nuevo.",
        slug="rate-limited",
        headers={"Retry-After": "60"},
    )


def register_app_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
