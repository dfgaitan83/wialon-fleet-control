"""Casos de uso de conductores y pasajeros (RF-08, RF-09, RF-16..18, RF-27, RF-28).

Las reglas de negocio viven AQUÍ (validaciones, duplicados, asignaciones); el
detalle de cómo Wialon guarda los datos (leer-fusionar-escribir) vive en el
adaptador. Cada escritura queda en la auditoría (RF-26).
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.application.audit_service import AuditService
from app.application.errors import Conflict, NotFound, ValidationFailed
from app.application.pagination import Page, PageRequest
from app.application.ports import UnitOfWork
from app.domain.fleet import FleetSnapshot, Person, PersonChanges, PersonKind, Vehicle
from app.domain.users import User

NAME_MAX = 50
CODE_MAX = 30
DESCRIPTION_MAX = 200
FIELD_KEY_MAX = 50
FIELD_VALUE_MAX = 200
MAX_CUSTOM_FIELDS = 30
_PHONE = re.compile(r"^\+?[0-9][0-9 ()-]{5,19}$")  # +57 300 000 0000, (601) 555-1234...
_LABELS: dict[PersonKind, str] = {"driver": "conductor", "passenger": "pasajero"}


class PeopleGateway(Protocol):
    async def snapshot(self) -> FleetSnapshot: ...
    async def create_person(self, kind: PersonKind, resource_id: int, data: PersonChanges) -> Person: ...
    async def update_person(
        self, kind: PersonKind, resource_id: int, person_id: int, changes: PersonChanges
    ) -> Person: ...
    async def delete_person(self, kind: PersonKind, resource_id: int, person_id: int) -> None: ...
    async def set_person_binding(
        self, kind: PersonKind, resource_id: int, person_id: int, unit_id: int, *, bind: bool
    ) -> None: ...


@dataclass(frozen=True)
class PersonView:
    person: Person
    vehicle_name: str | None  # nombre del vehículo vinculado (None = sin vehículo)


class PeopleService:
    def __init__(
        self, gateway: PeopleGateway, audit: AuditService, uow: UnitOfWork, clock: Callable[[], datetime]
    ) -> None:
        self._gateway = gateway
        self._audit = audit
        self._uow = uow
        self._clock = clock

    # ---------------------------------------------------------------- lectura
    async def list_people(
        self, kind: PersonKind, request: PageRequest, *, search: str | None = None, assigned: bool | None = None
    ) -> Page[PersonView]:
        snapshot = await self._gateway.snapshot()
        names = {v.id: v.name for v in snapshot.vehicles}
        term = search.strip().lower() if search and search.strip() else None
        people = [
            p
            for p in _people(snapshot, kind)
            if (term is None or term in p.name.lower() or term in p.code.lower())
            and (assigned is None or (p.vehicle_id is not None) == assigned)
        ]
        start = request.offset
        page = people[start : start + request.page_size]
        return Page(
            items=[PersonView(p, names.get(p.vehicle_id) if p.vehicle_id else None) for p in page],
            total=len(people), page=request.page, page_size=request.page_size,
        )

    async def get_person(self, kind: PersonKind, resource_id: int, person_id: int) -> PersonView:
        snapshot = await self._gateway.snapshot()
        person = _find(snapshot, kind, resource_id, person_id)
        names = {v.id: v.name for v in snapshot.vehicles}
        return PersonView(person, names.get(person.vehicle_id) if person.vehicle_id else None)

    # -------------------------------------------------------------- escritura
    async def create_person(
        self, actor: User, kind: PersonKind, data: PersonChanges, *, resource_id: int | None, ip: str | None
    ) -> Person:
        snapshot = await self._gateway.snapshot()
        target_resource = resource_id or snapshot.people_resource_id
        if target_resource is None:
            raise ValidationFailed("No hay un recurso de Wialon donde crear.", {"resource_id": ["Indica el recurso."]})
        _validate(data, creating=True)
        _ensure_unique_code(snapshot, kind, data.code, exclude=None)
        person = await self._gateway.create_person(kind, target_resource, data)
        await self._record(f"{kind}s.created", actor, person, ip, {"name": person.name, "code": person.code})
        return person

    async def update_person(
        self, actor: User, kind: PersonKind, resource_id: int, person_id: int, changes: PersonChanges, ip: str | None
    ) -> Person:
        snapshot = await self._gateway.snapshot()
        current = _find(snapshot, kind, resource_id, person_id)
        _validate(changes, creating=False)
        if changes.code is not None:
            _ensure_unique_code(snapshot, kind, changes.code, exclude=current)
        person = await self._gateway.update_person(kind, resource_id, person_id, changes)
        await self._record(f"{kind}s.updated", actor, person, ip, _changed_fields(current, changes))
        return person

    async def delete_person(
        self, actor: User, kind: PersonKind, resource_id: int, person_id: int, ip: str | None
    ) -> None:
        snapshot = await self._gateway.snapshot()
        current = _find(snapshot, kind, resource_id, person_id)
        await self._gateway.delete_person(kind, resource_id, person_id)
        await self._record(f"{kind}s.deleted", actor, current, ip, {"name": current.name})

    async def assign(
        self, actor: User, kind: PersonKind, vehicle_id: int, resource_id: int, person_id: int, ip: str | None
    ) -> Person:
        """Vincula a un vehículo (RF-09, RF-17). Errores claros: inexistente, ya asignado, ocupado."""
        snapshot = await self._gateway.snapshot()
        vehicle = _vehicle(snapshot, vehicle_id)
        person = _find(snapshot, kind, resource_id, person_id)
        if person.vehicle_id == vehicle_id:
            raise Conflict(f"El {_LABELS[kind]} ya está asignado a este vehículo.")
        if kind == "driver" and vehicle.driver is not None:
            raise Conflict(f"{vehicle.name} ya tiene conductor ({vehicle.driver.name}). Desvincúlalo primero.")
        if person.vehicle_id is not None:  # estaba en otro vehículo: se libera primero (sin dobles vínculos)
            await self._gateway.set_person_binding(kind, resource_id, person_id, person.vehicle_id, bind=False)
        await self._gateway.set_person_binding(kind, resource_id, person_id, vehicle_id, bind=True)
        await self._record(f"{kind}s.assigned", actor, person, ip, {"vehicle_id": vehicle_id, "vehicle": vehicle.name})
        return Person(**{**person.__dict__, "vehicle_id": vehicle_id})

    async def unassign(
        self, actor: User, kind: PersonKind, vehicle_id: int, resource_id: int, person_id: int, ip: str | None
    ) -> None:
        snapshot = await self._gateway.snapshot()
        vehicle = _vehicle(snapshot, vehicle_id)
        person = _find(snapshot, kind, resource_id, person_id)
        if person.vehicle_id != vehicle_id:
            raise Conflict(f"El {_LABELS[kind]} no está asignado a {vehicle.name}.")
        await self._gateway.set_person_binding(kind, resource_id, person_id, vehicle_id, bind=False)
        await self._record(f"{kind}s.unassigned", actor, person, ip, {"vehicle_id": vehicle_id, "vehicle": vehicle.name})

    async def _record(self, action: str, actor: User, person: Person, ip: str | None, details: dict) -> None:
        await self._audit.record(
            action, actor=actor, entity_type=action.split(".")[0][:-1], entity_id=f"{person.resource_id}:{person.id}",
            ip_address=ip, details=details,
        )
        await self._uow.commit()


# ------------------------------------------------------------------ reglas
def _people(snapshot: FleetSnapshot, kind: PersonKind) -> tuple[Person, ...]:
    return snapshot.drivers if kind == "driver" else snapshot.passengers


def _find(snapshot: FleetSnapshot, kind: PersonKind, resource_id: int, person_id: int) -> Person:
    for person in _people(snapshot, kind):
        if person.id == person_id and person.resource_id == resource_id:
            return person
    raise NotFound(f"El {_LABELS[kind]} no existe.")


def _vehicle(snapshot: FleetSnapshot, vehicle_id: int) -> Vehicle:
    for vehicle in snapshot.vehicles:
        if vehicle.id == vehicle_id:
            return vehicle
    raise NotFound("El vehículo no existe o no es visible para esta cuenta.")


def _ensure_unique_code(snapshot: FleetSnapshot, kind: PersonKind, code: str | None, exclude: Person | None) -> None:
    """RF-18: el código identifica a la persona; no puede repetirse (sin distinguir mayúsculas)."""
    if not code:
        return
    for person in _people(snapshot, kind):
        if person.code.strip().lower() == code.strip().lower() and person is not exclude:
            raise Conflict(f"Ya existe un {_LABELS[kind]} con el código {code}.")


def _validate(data: PersonChanges, *, creating: bool) -> None:
    errors: dict[str, list[str]] = {}
    if creating or data.name is not None:
        name = (data.name or "").strip()
        if not name or len(name) > NAME_MAX:
            errors["name"] = [f"El nombre es obligatorio (máximo {NAME_MAX} caracteres)."]
    if data.code is not None and len(data.code) > CODE_MAX:
        errors["code"] = [f"Máximo {CODE_MAX} caracteres."]
    if data.description is not None and len(data.description) > DESCRIPTION_MAX:
        errors["description"] = [f"Máximo {DESCRIPTION_MAX} caracteres."]
    if data.phone and not _PHONE.match(data.phone.strip()):
        errors["phone"] = ["Teléfono no válido (ej. +57 300 000 0000)."]
    if data.custom_fields is not None:
        problems = _custom_field_errors(data.custom_fields)
        if problems:
            errors["custom_fields"] = problems
    if errors:
        raise ValidationFailed("Revisa los datos.", errors)


def _custom_field_errors(fields: dict[str, str]) -> list[str]:
    problems: list[str] = []
    if len(fields) > MAX_CUSTOM_FIELDS:
        problems.append(f"Máximo {MAX_CUSTOM_FIELDS} campos personalizados.")
    if any(not key.strip() or len(key) > FIELD_KEY_MAX for key in fields):
        problems.append(f"Cada campo necesita un nombre (máximo {FIELD_KEY_MAX} caracteres).")
    if any(len(value) > FIELD_VALUE_MAX for value in fields.values()):
        problems.append(f"Cada valor admite máximo {FIELD_VALUE_MAX} caracteres.")
    return problems


def _changed_fields(current: Person, changes: PersonChanges) -> dict[str, object]:
    """Para la auditoría: qué campos cambiaron (los valores de jp se omiten: pueden ser personales)."""
    fields = {
        "name": (current.name, changes.name),
        "code": (current.code, changes.code),
        "description": (current.description, changes.description),
        "phone": (current.phone, changes.phone),
    }
    diff: dict[str, object] = {k: {"from": old, "to": new} for k, (old, new) in fields.items() if new is not None and new != old}
    if changes.custom_fields is not None and changes.custom_fields != current.custom_fields:
        diff["custom_fields"] = sorted(changes.custom_fields)  # solo los nombres de los campos
    return diff
