"""Cookies de sesión y protección CSRF (SEG-07, SEG-11).

Tres cookies, cada una con el MÍNIMO alcance posible:

| Cookie          | HttpOnly | SameSite | Path            | Vida   | Para qué                         |
|-----------------|----------|----------|-----------------|--------|----------------------------------|
| fleet_access    | sí       | Lax      | /api            | 15 min | JWT de acceso                    |
| fleet_refresh   | sí       | Strict   | /api/v1/auth    | 7 días | solo viaja a refresh/logout      |
| fleet_csrf      | NO       | Lax      | /               | 7 días | el JS lo copia en X-CSRF-Token   |

- HttpOnly: el JavaScript (y por tanto un XSS) no puede leer los tokens.
- Secure: solo por HTTPS (configurable para pruebas locales sin TLS).
- CSRF "double submit": en peticiones que modifican datos, el header
  ``X-CSRF-Token`` debe coincidir con la cookie ``fleet_csrf``. Otro sitio puede
  hacer que el navegador ENVÍE nuestras cookies, pero no puede LEERLAS para
  copiar el valor en el header. La comparación es en tiempo constante.
"""

import secrets
from datetime import timedelta

from fastapi import Request, Response

from app.application.errors import PermissionDenied
from app.core.config import Settings

ACCESS_COOKIE = "fleet_access"
REFRESH_COOKIE = "fleet_refresh"
CSRF_COOKIE = "fleet_csrf"
CSRF_HEADER = "X-CSRF-Token"

ACCESS_PATH = "/api"
REFRESH_PATH = "/api/v1/auth"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def set_session_cookies(response: Response, settings: Settings, access_token: str, refresh_token: str) -> None:
    access_ttl = int(timedelta(minutes=settings.access_token_minutes).total_seconds())
    refresh_ttl = int(timedelta(days=settings.refresh_token_days).total_seconds())
    common = {"secure": settings.cookie_secure}
    response.set_cookie(
        ACCESS_COOKIE, access_token, max_age=access_ttl, httponly=True, samesite="lax",
        path=ACCESS_PATH, **common,
    )
    response.set_cookie(
        REFRESH_COOKIE, refresh_token, max_age=refresh_ttl, httponly=True, samesite="strict",
        path=REFRESH_PATH, **common,
    )
    # Token CSRF nuevo en cada login/refresh (rotación junto con la sesión).
    response.set_cookie(
        CSRF_COOKIE, secrets.token_urlsafe(32), max_age=refresh_ttl, httponly=False, samesite="lax",
        path="/", **common,
    )


def clear_session_cookies(response: Response, settings: Settings) -> None:
    for name, path in ((ACCESS_COOKIE, ACCESS_PATH), (REFRESH_COOKIE, REFRESH_PATH), (CSRF_COOKIE, "/")):
        response.delete_cookie(name, path=path, secure=settings.cookie_secure, httponly=name != CSRF_COOKIE)


def verify_csrf(request: Request) -> None:
    """Dependencia: exige el header CSRF en métodos que modifican datos."""
    if request.method in SAFE_METHODS:
        return
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get(CSRF_HEADER)
    if not cookie or not header or not secrets.compare_digest(cookie, header):
        raise PermissionDenied("Falta o no coincide el token CSRF. Recarga la página e inténtalo de nuevo.")
