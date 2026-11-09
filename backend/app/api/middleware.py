"""Middleware HTTP: cabeceras de seguridad, Cache-Control y log de peticiones (SEG-05, ARQ-07)."""

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request, Response

logger = structlog.get_logger("app.http")

REQUEST_ID_HEADER = "X-Request-ID"
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")

# La API solo devuelve JSON: la CSP más estricta posible (no carga nada, no se incrusta).
_API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
# Swagger UI carga sus scripts/estilos desde jsDelivr y usa un script inline (FastAPI).
_DOCS_CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; "
    "frame-ancestors 'none'"
)


def _security_headers(path: str, hsts: bool) -> dict[str, str]:
    headers = {
        "X-Content-Type-Options": "nosniff",  # el navegador no "adivina" tipos de contenido
        "X-Frame-Options": "DENY",  # anti-clickjacking (navegadores antiguos)
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Content-Security-Policy": _DOCS_CSP if path.startswith(_DOCS_PATHS) else _API_CSP,
        # Datos de flota y sesión: que ningún proxy ni navegador los guarde en caché.
        "Cache-Control": "no-store",
    }
    if hsts:  # solo con HTTPS real (producción): obliga al navegador a usar siempre HTTPS
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return headers


def register_middleware(app: FastAPI, *, hsts: bool) -> None:
    @app.middleware("http")
    async def security_and_logging(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Id de petición para correlacionar logs (se reutiliza si llega desde el proxy).
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
        response.headers.update(_security_headers(request.url.path, hsts))
        response.headers[REQUEST_ID_HEADER] = request_id
        # Se registra ruta y estado, NUNCA query string, cuerpo ni cookies (pueden llevar datos personales).
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
            request_id=request_id,
        )
        return response
