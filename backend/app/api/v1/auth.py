"""Endpoints de autenticación: /api/v1/auth/* (RF-04, RF-06, SEG-07, SEG-11)."""

from fastapi import APIRouter, Depends, Request, Response, status
from slowapi import Limiter

from app.api.cookies import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    clear_session_cookies,
    set_session_cookies,
    verify_csrf,
)
from app.api.deps import AuthServiceDep, SessionUserDep, client_ip
from app.api.v1.schemas import ChangePasswordRequest, LoginRequest, SessionOut, UserOut
from app.application.auth_service import AuthSession
from app.application.errors import InvalidSession
from app.core.config import Settings

_PROBLEM = {"model": None, "content": {"application/problem+json": {}}}


def _session_response(response: Response, settings: Settings, session: AuthSession) -> SessionOut:
    set_session_cookies(response, settings, session.access_token, session.refresh_token)
    return SessionOut(user=UserOut.from_domain(session.user))


def build_auth_router(limiter: Limiter, settings: Settings) -> APIRouter:
    """Fábrica: el limitador y su cuota se inyectan (cada app/test tiene su propio contador)."""
    router = APIRouter(prefix="/auth", tags=["auth"])

    @router.post(
        "/login",
        response_model=SessionOut,
        responses={401: _PROBLEM, 422: _PROBLEM, 429: _PROBLEM},
        summary="Iniciar sesión con correo y contraseña",
    )
    @limiter.limit(settings.login_rate_limit)  # SEG-07: rate limit por IP
    async def login(request: Request, response: Response, body: LoginRequest, auth: AuthServiceDep) -> SessionOut:
        # Sin CSRF: aún no hay sesión que proteger. La respuesta crea la cookie CSRF.
        session = await auth.login(body.email, body.password, client_ip(request))
        return _session_response(response, settings, session)

    @router.post(
        "/refresh",
        response_model=SessionOut,
        responses={401: _PROBLEM, 403: _PROBLEM},
        dependencies=[Depends(verify_csrf)],
        summary="Renovar la sesión (rota el refresh token)",
    )
    async def refresh(request: Request, response: Response, auth: AuthServiceDep) -> SessionOut:
        session = await auth.refresh(request.cookies.get(REFRESH_COOKIE), client_ip(request))
        return _session_response(response, settings, session)

    @router.post(
        "/logout",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Depends(verify_csrf)],
        summary="Cerrar sesión (invalida el refresh token en el servidor)",
    )
    async def logout(request: Request, auth: AuthServiceDep) -> Response:
        # Logout tolerante: aunque el access haya expirado, se revoca el refresh y se borran cookies.
        try:
            actor = await auth.current_user(request.cookies.get(ACCESS_COOKIE))
        except InvalidSession:
            actor = None  # sin access válido igualmente se cierra la sesión del refresh
        await auth.logout(request.cookies.get(REFRESH_COOKIE), actor, client_ip(request))
        response = Response(status_code=status.HTTP_204_NO_CONTENT)
        clear_session_cookies(response, settings)
        return response

    @router.get("/me", response_model=UserOut, responses={401: _PROBLEM}, summary="Usuario de la sesión actual")
    async def me(user: SessionUserDep) -> UserOut:
        return UserOut.from_domain(user)

    @router.post(
        "/change-password",
        response_model=SessionOut,
        responses={401: _PROBLEM, 403: _PROBLEM, 422: _PROBLEM},
        dependencies=[Depends(verify_csrf)],
        summary="Cambiar la contraseña (obligatorio en el primer inicio de sesión)",
    )
    async def change_password(
        request: Request, response: Response, body: ChangePasswordRequest, user: SessionUserDep,
        auth: AuthServiceDep,
    ) -> SessionOut:
        session = await auth.change_password(user, body.current_password, body.new_password, client_ip(request))
        return _session_response(response, settings, session)

    return router
