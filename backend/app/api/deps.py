"""Dependencias de FastAPI: composición por petición y control de acceso (SEG-01).

Junto con ``app/main.py`` es raíz de composición: el único sitio de la API que
conoce las implementaciones concretas (repositorios SQL, Argon2, JWT).

Uso en un endpoint::

    @router.get("/drivers")
    async def list_drivers(user: User = Depends(require_permission(Permission.DRIVERS_READ))): ...

Denegar por defecto: sin cookie válida -> 401; sin el permiso -> 403; con
contraseña pendiente de cambio -> 403 (RF-06). Los endpoints NUNCA preguntan por
el rol, solo por el permiso.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated

import structlog
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cookies import ACCESS_COOKIE
from app.application.audit_service import AuditService
from app.application.auth_service import AuthPolicy, AuthService
from app.application.errors import PasswordChangeRequired, PermissionDenied
from app.application.fleet_service import FleetService
from app.application.people_service import PeopleService
from app.application.user_service import UserService
from app.core.clock import utc_now
from app.core.config import Settings
from app.domain.permissions import Permission
from app.domain.status import ThresholdStatusStrategy
from app.domain.users import User
from app.infrastructure.db.repositories import (
    SqlAuditLog,
    SqlRefreshTokenStore,
    SqlRoleCatalog,
    SqlUnitOfWork,
    SqlUserRepository,
)

logger = structlog.get_logger(__name__)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Una sesión de BD por petición. Lo que el caso de uso no confirme se descarta al cerrar."""
    async with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_audit_service(session: SessionDep) -> AuditService:
    return AuditService(SqlAuditLog(session), clock=utc_now)


def get_auth_service(request: Request, session: SessionDep) -> AuthService:
    settings: Settings = request.app.state.settings
    return AuthService(
        users=SqlUserRepository(session, clock=utc_now),
        refresh_tokens=SqlRefreshTokenStore(session, clock=utc_now),
        hasher=request.app.state.password_hasher,
        access_tokens=request.app.state.access_tokens,
        audit=get_audit_service(session),
        uow=SqlUnitOfWork(session),
        clock=utc_now,
        policy=AuthPolicy(
            max_failed_attempts=settings.login_max_attempts,
            lockout=request.app.state.lockout,
            refresh_ttl=request.app.state.refresh_ttl,
        ),
    )


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def get_user_service(request: Request, session: SessionDep) -> UserService:
    return UserService(
        users=SqlUserRepository(session, clock=utc_now),
        roles=SqlRoleCatalog(session),
        refresh_tokens=SqlRefreshTokenStore(session, clock=utc_now),
        hasher=request.app.state.password_hasher,
        audit=get_audit_service(session),
        uow=SqlUnitOfWork(session),
        clock=utc_now,
    )


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


def get_fleet_service(request: Request) -> FleetService:
    # El gateway es UNO por app (app.state): comparte la caché TTL y la sesión de Wialon.
    return FleetService(request.app.state.fleet_gateway, ThresholdStatusStrategy(), clock=utc_now)


FleetServiceDep = Annotated[FleetService, Depends(get_fleet_service)]


def get_people_service(request: Request, session: SessionDep) -> PeopleService:
    return PeopleService(
        request.app.state.fleet_gateway, get_audit_service(session), SqlUnitOfWork(session), clock=utc_now
    )


PeopleServiceDep = Annotated[PeopleService, Depends(get_people_service)]


def client_ip(request: Request) -> str | None:
    """IP del cliente. En Render/Vercel la fija uvicorn con --proxy-headers (X-Forwarded-For)."""
    return request.client.host if request.client else None


async def get_session_user(request: Request, auth: AuthServiceDep) -> User:
    """Usuario autenticado, AUNQUE deba cambiar su contraseña (solo para /me, cambio y logout)."""
    return await auth.current_user(request.cookies.get(ACCESS_COOKIE))


SessionUserDep = Annotated[User, Depends(get_session_user)]


def require_permission(permission: Permission) -> Callable[..., Awaitable[User]]:
    """Fábrica de dependencias: exige sesión válida, contraseña al día y el permiso indicado."""

    async def dependency(request: Request, user: SessionUserDep, session: SessionDep) -> User:
        if user.must_change_password:
            raise PasswordChangeRequired
        if not user.can(permission):
            # SEG-09: el acceso denegado queda auditado (posible intento de escalada).
            await get_audit_service(session).record(
                "auth.access_denied", actor=user, ip_address=client_ip(request),
                details={"permission": str(permission), "path": request.url.path},
            )
            await session.commit()
            logger.warning("access_denied", user_id=user.id, permission=str(permission))
            raise PermissionDenied
        return user

    return dependency
