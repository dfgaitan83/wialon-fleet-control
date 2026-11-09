"""Formato de error único: Problem Details (RFC 9457, sucesor del RFC 7807) — ARQ-04.

TODA respuesta de error de la API tiene esta forma (el frontend la valida en
``frontend/src/shared/api/problem.ts``)::

    {"type": "/problems/invalid-credentials", "title": "...", "status": 401,
     "detail": "...", "instance": "/api/v1/auth/login", "errors": {"campo": ["..."]}}

SEG-10: los errores inesperados responden un 500 genérico. El detalle técnico
(traza) va SOLO al log del servidor, nunca al cliente.
"""

from http import HTTPStatus
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_CONTENT_TYPE = "application/problem+json"

logger = structlog.get_logger(__name__)

# Títulos en español (es-CO) por código HTTP.
_TITLES: dict[int, str] = {
    400: "Solicitud inválida",
    401: "No autenticado",
    403: "Acceso denegado",
    404: "Recurso no encontrado",
    405: "Método no permitido",
    409: "Conflicto",
    422: "Revisa los datos enviados",
    429: "Demasiadas solicitudes",
    500: "Error interno del servidor",
    503: "Servicio no disponible",
}


def problem_response(
    request: Request,
    status: int,
    detail: str | None = None,
    *,
    slug: str | None = None,
    errors: dict[str, list[str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Construye una respuesta Problem Details."""
    body: dict[str, Any] = {
        "type": f"/problems/{slug}" if slug else "about:blank",
        "title": _TITLES.get(status, HTTPStatus(status).phrase),
        "status": status,
        "instance": request.url.path,
    }
    if detail:
        body["detail"] = detail
    if errors:
        body["errors"] = errors
    return JSONResponse(body, status_code=status, media_type=PROBLEM_CONTENT_TYPE, headers=headers)


def _validation_errors(exc: RequestValidationError) -> dict[str, list[str]]:
    """Errores de Pydantic -> {campo: [mensajes]} (sin el valor recibido: podría ser sensible)."""
    errors: dict[str, list[str]] = {}
    for err in exc.errors():
        loc = [str(part) for part in err.get("loc", ()) if part not in ("body", "query", "path")]
        field = ".".join(loc) or "request"
        errors.setdefault(field, []).append(str(err.get("msg", "Valor inválido")))
    return errors


async def _http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    detail = exc.detail if isinstance(exc.detail, str) else None
    return problem_response(request, exc.status_code, detail, headers=getattr(exc, "headers", None))


async def _validation_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    return problem_response(
        request, 422, "Uno o más campos no son válidos.", slug="validation", errors=_validation_errors(exc)
    )


async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    # La traza completa queda en el log del servidor; el cliente solo ve un mensaje genérico.
    logger.exception("unhandled_error", path=request.url.path, method=request.method)
    return problem_response(request, 500, "Ocurrió un error inesperado. Intenta de nuevo más tarde.")


def register_problem_handlers(app: FastAPI) -> None:
    """Registra los manejadores genéricos (los de negocio están en ``app/api/errors.py``)."""
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(Exception, _unhandled_handler)
