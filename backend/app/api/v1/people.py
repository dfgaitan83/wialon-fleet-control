"""Endpoints de conductores y pasajeros (RF-08, RF-09, RF-16..18, RF-27, RF-28).

Un solo constructor de router para los dos tipos (DRY): mismas reglas, distinto
permiso y prefijo. Los ids de Wialon son únicos DENTRO de un recurso, por eso la
ruta lleva ``/{resource_id}/{person_id}``.

    GET    /drivers?page&page_size&q&assigned      (drivers:read)
    POST   /drivers                                 (drivers:write)
    GET    /drivers/{rid}/{id}                      (drivers:read)
    PATCH  /drivers/{rid}/{id}                      (drivers:write)  leer-fusionar-escribir
    DELETE /drivers/{rid}/{id}                      (drivers:write)
    PUT    /vehicles/{vid}/drivers/{rid}/{id}       (assignments:write)  vincular
    DELETE /vehicles/{vid}/drivers/{rid}/{id}       (assignments:write)  desvincular
    (idéntico para /passengers)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.cookies import verify_csrf
from app.api.deps import PeopleServiceDep, client_ip, require_permission
from app.api.v1.schemas import PageOut
from app.application.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, PageRequest
from app.application.people_service import PersonView
from app.domain.fleet import PersonChanges, PersonKind
from app.domain.permissions import Permission
from app.domain.users import User

_PROBLEM = {"model": None, "content": {"application/problem+json": {}}}
_ERRORS = {401: _PROBLEM, 403: _PROBLEM, 404: _PROBLEM, 409: _PROBLEM, 422: _PROBLEM, 503: _PROBLEM}


class VehicleRefOut(BaseModel):
    id: int
    name: str


class PersonOut(BaseModel):
    id: int
    resource_id: int
    name: str
    code: str
    description: str
    phone: str
    custom_fields: dict[str, str]
    vehicle: VehicleRefOut | None  # null = sin vehículo asignado

    @classmethod
    def from_view(cls, view: PersonView) -> "PersonOut":
        p = view.person
        vehicle = VehicleRefOut(id=p.vehicle_id, name=view.vehicle_name or f"Unidad {p.vehicle_id}") if p.vehicle_id else None
        return cls(
            id=p.id, resource_id=p.resource_id, name=p.name, code=p.code, description=p.description,
            phone=p.phone, custom_fields=p.custom_fields, vehicle=vehicle,
        )


class PersonCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=50)
    code: str = Field(default="", max_length=30)
    description: str = Field(default="", max_length=200)
    phone: str = Field(default="", max_length=25)
    custom_fields: dict[str, str] = Field(default_factory=dict)
    resource_id: int | None = None  # por defecto, el recurso de personas de la cuenta


class PersonUpdate(BaseModel):
    """PATCH: solo cambia lo enviado. ``custom_fields`` reemplaza el conjunto COMPLETO (así
    se pueden crear, editar y borrar campos); si se omite, se conservan (RF-27)."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=50)
    code: str | None = Field(default=None, max_length=30)
    description: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=25)
    custom_fields: dict[str, str] | None = None


def build_people_router(kind: PersonKind, prefix: str, read: Permission, write: Permission) -> APIRouter:
    reader = Annotated[User, Depends(require_permission(read))]
    writer = Annotated[User, Depends(require_permission(write))]
    assigner = Annotated[User, Depends(require_permission(Permission.ASSIGNMENTS_WRITE))]
    router = APIRouter(tags=[prefix], responses=_ERRORS)

    @router.get(f"/{prefix}", response_model=PageOut[PersonOut], name=f"list_{prefix}")
    async def list_people(
        _user: reader,
        service: PeopleServiceDep,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
        q: Annotated[str | None, Query(max_length=100, description="Busca en nombre y código")] = None,
        assigned: Annotated[bool | None, Query(description="true: con vehículo; false: sin vehículo")] = None,
    ) -> PageOut[PersonOut]:
        result = await service.list_people(kind, PageRequest(page, page_size), search=q, assigned=assigned)
        return PageOut(
            items=[PersonOut.from_view(v) for v in result.items],
            total=result.total, page=result.page, page_size=result.page_size,
        )

    @router.get(f"/{prefix}/{{resource_id}}/{{person_id}}", response_model=PersonOut, name=f"get_{kind}")
    async def get_person(resource_id: int, person_id: int, _user: reader, service: PeopleServiceDep) -> PersonOut:
        return PersonOut.from_view(await service.get_person(kind, resource_id, person_id))

    @router.post(
        f"/{prefix}", response_model=PersonOut, status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(verify_csrf)], name=f"create_{kind}",
    )
    async def create_person(request: Request, body: PersonCreate, actor: writer, service: PeopleServiceDep) -> PersonOut:
        data = PersonChanges(
            name=body.name.strip(), code=body.code.strip(), description=body.description.strip(),
            phone=body.phone.strip(), custom_fields=body.custom_fields,
        )
        person = await service.create_person(actor, kind, data, resource_id=body.resource_id, ip=client_ip(request))
        return PersonOut.from_view(PersonView(person, None))

    @router.patch(
        f"/{prefix}/{{resource_id}}/{{person_id}}", response_model=PersonOut,
        dependencies=[Depends(verify_csrf)], name=f"update_{kind}",
    )
    async def update_person(
        resource_id: int, person_id: int, request: Request, body: PersonUpdate, actor: writer,
        service: PeopleServiceDep,
    ) -> PersonOut:
        changes = PersonChanges(**body.model_dump())
        await service.update_person(actor, kind, resource_id, person_id, changes, client_ip(request))
        return PersonOut.from_view(await service.get_person(kind, resource_id, person_id))

    @router.delete(
        f"/{prefix}/{{resource_id}}/{{person_id}}", status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Depends(verify_csrf)], name=f"delete_{kind}",
    )
    async def delete_person(
        resource_id: int, person_id: int, request: Request, actor: writer, service: PeopleServiceDep
    ) -> Response:
        await service.delete_person(actor, kind, resource_id, person_id, client_ip(request))
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.put(
        f"/vehicles/{{vehicle_id}}/{prefix}/{{resource_id}}/{{person_id}}", status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Depends(verify_csrf)], name=f"assign_{kind}",
    )
    async def assign(
        vehicle_id: int, resource_id: int, person_id: int, request: Request, actor: assigner, service: PeopleServiceDep
    ) -> Response:
        await service.assign(actor, kind, vehicle_id, resource_id, person_id, client_ip(request))
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.delete(
        f"/vehicles/{{vehicle_id}}/{prefix}/{{resource_id}}/{{person_id}}", status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Depends(verify_csrf)], name=f"unassign_{kind}",
    )
    async def unassign(
        vehicle_id: int, resource_id: int, person_id: int, request: Request, actor: assigner, service: PeopleServiceDep
    ) -> Response:
        await service.unassign(actor, kind, vehicle_id, resource_id, person_id, client_ip(request))
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router


drivers_router = build_people_router("driver", "drivers", Permission.DRIVERS_READ, Permission.DRIVERS_WRITE)
passengers_router = build_people_router(
    "passenger", "passengers", Permission.PASSENGERS_READ, Permission.PASSENGERS_WRITE
)
