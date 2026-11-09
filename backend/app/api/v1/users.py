"""Endpoints de gestión de usuarios: /api/v1/users y /api/v1/roles (RF-06, solo Admin).

Lectura exige ``users:read``; escritura ``users:write`` + CSRF. El rol del Admin
nunca se menciona aquí: solo permisos (matriz 5.3 en la BD).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.cookies import verify_csrf
from app.api.deps import UserServiceDep, client_ip, require_permission
from app.api.v1.schemas import (
    CreatedUserOut,
    CreateUserRequest,
    PageOut,
    RoleOut,
    TemporaryPasswordOut,
    UpdateUserRequest,
    UserAdminOut,
)
from app.application.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, PageRequest
from app.core.clock import utc_now
from app.domain.permissions import Permission
from app.domain.users import User

_PROBLEM = {"model": None, "content": {"application/problem+json": {}}}
_ERRORS = {401: _PROBLEM, 403: _PROBLEM, 404: _PROBLEM, 409: _PROBLEM, 422: _PROBLEM}

UsersReader = Annotated[User, Depends(require_permission(Permission.USERS_READ))]
UsersWriter = Annotated[User, Depends(require_permission(Permission.USERS_WRITE))]

router = APIRouter(tags=["users"], responses=_ERRORS)


@router.get("/users", response_model=PageOut[UserAdminOut], summary="Listar usuarios (paginado)")
async def list_users(
    _actor: UsersReader,
    service: UserServiceDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    q: Annotated[str | None, Query(max_length=100, description="Busca en correo y nombre")] = None,
) -> PageOut[UserAdminOut]:
    result = await service.list_users(PageRequest(page=page, page_size=page_size), q)
    now = utc_now()
    return PageOut(
        items=[UserAdminOut.from_user(u, now) for u in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/users/{user_id}", response_model=UserAdminOut, summary="Detalle de un usuario")
async def get_user(user_id: int, _actor: UsersReader, service: UserServiceDep) -> UserAdminOut:
    return UserAdminOut.from_user(await service.get_user(user_id), utc_now())


@router.post(
    "/users",
    response_model=CreatedUserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
    summary="Crear usuario (devuelve una contraseña temporal UNA sola vez)",
)
async def create_user(
    request: Request, body: CreateUserRequest, actor: UsersWriter, service: UserServiceDep
) -> CreatedUserOut:
    created = await service.create_user(
        actor, email=body.email, full_name=body.full_name, role=body.role, ip=client_ip(request)
    )
    return CreatedUserOut(
        user=UserAdminOut.from_user(created.user, utc_now()), temporary_password=created.temporary_password
    )


@router.patch(
    "/users/{user_id}",
    response_model=UserAdminOut,
    dependencies=[Depends(verify_csrf)],
    summary="Cambiar nombre, rol o activar/desactivar",
)
async def update_user(
    user_id: int, request: Request, body: UpdateUserRequest, actor: UsersWriter, service: UserServiceDep
) -> UserAdminOut:
    user = await service.update_user(
        actor, user_id, full_name=body.full_name, role=body.role, is_active=body.is_active,
        ip=client_ip(request),
    )
    return UserAdminOut.from_user(user, utc_now())


@router.post(
    "/users/{user_id}/reset-password",
    response_model=TemporaryPasswordOut,
    dependencies=[Depends(verify_csrf)],
    summary="Restablecer credenciales (nueva contraseña temporal, cierra sus sesiones)",
)
async def reset_password(
    user_id: int, request: Request, actor: UsersWriter, service: UserServiceDep
) -> TemporaryPasswordOut:
    temporary = await service.reset_password(actor, user_id, client_ip(request))
    return TemporaryPasswordOut(temporary_password=temporary)


@router.get("/roles", response_model=list[RoleOut], summary="Roles disponibles y sus permisos")
async def list_roles(_actor: UsersReader, service: UserServiceDep) -> list[RoleOut]:
    return [
        RoleOut(name=r.name, label=r.label, permissions=sorted(r.permissions))
        for r in await service.list_roles()
    ]
