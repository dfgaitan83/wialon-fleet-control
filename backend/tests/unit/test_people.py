"""Conductores y pasajeros: adaptador (leer-fusionar-escribir, RF-27), reglas del
servicio (RF-18, RF-09) y autorización por rol en la API (TST-02). Sin Wialon real."""

from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI

from app.application.audit_service import AuditService
from app.application.errors import Conflict, NotFound, ValidationFailed
from app.application.pagination import PageRequest
from app.application.people_service import PeopleService
from app.domain.fleet import DriverRef, FleetSnapshot, Person, PersonChanges, Vehicle
from app.domain.users import User
from app.infrastructure.wialon.errors import WialonConflict
from app.infrastructure.wialon.people_writer import WialonPeopleWriter
from tests.conftest import create_user, csrf_headers, login

NOW = datetime(2026, 11, 9, 1, 0, tzinfo=UTC)
RID = 100
ACTOR = User(id=1, email="a@flota.example.com", full_name="A", password_hash="x", role="admin", permissions=frozenset())


# ------------------------------------------------- adaptador (RF-27 en Wialon)


class FakeWialonClient:
    """Imita la semántica VERIFICADA: el update reemplaza todo (omitir jp lo borra)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.tag = {"id": 5, "n": "Ana", "c": "P-1", "ds": "", "p": "", "jp": {"Ruta": "A", "Colegio": "X"}, "bu": 0}

    async def search_item(self, item_id: int, flags: int) -> dict:
        return {"id": item_id, "tags": {"5": dict(self.tag)}}

    async def call(self, svc: str, params: dict) -> object:
        self.calls.append((svc, params))
        if params.get("callMode") == "update":
            self.tag = {"id": 5, "n": params["n"], "c": params["c"], "ds": params["ds"], "p": params["p"],
                        "jp": params.get("jp", {}), "bu": 0}  # sin jp -> {} como Wialon
            return [5, self.tag]
        return {}


async def test_renaming_a_passenger_keeps_its_custom_fields() -> None:
    """RF-27: cambiar SOLO el nombre reenvía el jp actual; si no, Wialon lo borraría."""
    client = FakeWialonClient()
    writer = WialonPeopleWriter(client)  # type: ignore[arg-type]

    updated = await writer.update("passenger", RID, 5, PersonChanges(name="Ana María"))

    svc, params = client.calls[-1]
    assert svc == "resource/update_tag"
    assert params["jp"] == {"Ruta": "A", "Colegio": "X"}  # el jp viajó completo
    assert (params["n"], params["c"]) == ("Ana María", "P-1")  # lo no tocado, fusionado
    assert updated.custom_fields == {"Ruta": "A", "Colegio": "X"}


async def test_custom_fields_can_be_replaced_to_add_edit_and_delete() -> None:
    client = FakeWialonClient()
    writer = WialonPeopleWriter(client)  # type: ignore[arg-type]

    updated = await writer.update("passenger", RID, 5, PersonChanges(custom_fields={"Ruta": "B"}))

    assert updated.custom_fields == {"Ruta": "B"}  # "Colegio" borrado a propósito
    assert updated.name == "Ana"  # el nombre se conserva


async def test_repeated_unique_property_becomes_a_clear_conflict() -> None:
    """Wialon 1002 (p. ej. teléfono de conductor repetido, verificado) -> 409 con mensaje claro."""

    class RejectingClient(FakeWialonClient):
        async def call(self, svc: str, params: dict) -> object:
            raise WialonConflict(1002, "Ya existe")

    writer = WialonPeopleWriter(RejectingClient())  # type: ignore[arg-type]

    with pytest.raises(Conflict, match="teléfono o código"):
        await writer.create("driver", RID, PersonChanges(name="Ana", phone="+573000000000"))


async def test_binding_uses_the_verified_parameters() -> None:
    client = FakeWialonClient()
    writer = WialonPeopleWriter(client)  # type: ignore[arg-type]

    await writer.set_binding("driver", RID, 7, 900, bind=True)
    await writer.set_binding("driver", RID, 7, 900, bind=False)

    assert client.calls == [
        ("resource/bind_unit_driver", {"resourceId": RID, "driverId": 7, "unitId": 900, "time": 0, "mode": True}),
        ("resource/bind_unit_driver", {"resourceId": RID, "driverId": 7, "unitId": 900, "time": 0, "mode": False}),
    ]


# ------------------------------------------------------------- servicio


class FakeGateway:
    def __init__(self, drivers=(), passengers=(), vehicles=()) -> None:
        self.state = FleetSnapshot(
            vehicles=tuple(vehicles), total_drivers=len(drivers), total_passengers=len(passengers),
            fetched_at=NOW, drivers=tuple(drivers), passengers=tuple(passengers), people_resource_id=RID,
        )
        self.bindings: list[tuple] = []
        self.created: list[PersonChanges] = []

    async def snapshot(self) -> FleetSnapshot:
        return self.state

    async def create_person(self, kind, resource_id, data):
        self.created.append(data)
        return Person(id=99, resource_id=resource_id, name=data.name or "", code=data.code or "")

    async def update_person(self, kind, resource_id, person_id, changes):
        return Person(id=person_id, resource_id=resource_id, name=changes.name or "x")

    async def delete_person(self, kind, resource_id, person_id):
        return None

    async def set_person_binding(self, kind, resource_id, person_id, unit_id, *, bind):
        self.bindings.append((kind, person_id, unit_id, bind))


class FakeAuditLog:
    def __init__(self) -> None:
        self.entries: list = []

    async def add(self, entry) -> None:
        self.entries.append(entry)


class FakeUow:
    async def commit(self) -> None:
        return None


def _service(gateway: FakeGateway) -> tuple[PeopleService, FakeAuditLog]:
    log = FakeAuditLog()
    return PeopleService(gateway, AuditService(log, clock=lambda: NOW), FakeUow(), clock=lambda: NOW), log


DRIVER = Person(id=1, resource_id=RID, name="Carlos Pérez", code="C-01")
BUS = Vehicle(id=900, name="Bus 1", position=None)


async def test_duplicate_driver_code_is_rejected() -> None:
    service, _ = _service(FakeGateway(drivers=[DRIVER]))

    with pytest.raises(Conflict):
        await service.create_person(ACTOR, "driver", PersonChanges(name="Otro", code="c-01"), resource_id=None, ip=None)


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        (PersonChanges(name="   "), "name"),
        (PersonChanges(name="Ok", phone="abc"), "phone"),
        (PersonChanges(name="Ok", custom_fields={"": "x"}), "custom_fields"),
    ],
)
async def test_invalid_data_is_rejected_with_field_errors(changes: PersonChanges, field: str) -> None:
    service, _ = _service(FakeGateway())

    with pytest.raises(ValidationFailed) as exc_info:
        await service.create_person(ACTOR, "passenger", changes, resource_id=None, ip=None)

    assert field in exc_info.value.errors


async def test_create_goes_to_the_people_resource_and_is_audited() -> None:
    gateway = FakeGateway()
    service, log = _service(gateway)

    person = await service.create_person(ACTOR, "passenger", PersonChanges(name="Ana", code="P-1"), resource_id=None, ip="1.1.1.1")

    assert person.resource_id == RID
    assert [e.action for e in log.entries] == ["passengers.created"]


async def test_assign_to_unknown_vehicle_is_not_found() -> None:
    service, _ = _service(FakeGateway(drivers=[DRIVER]))

    with pytest.raises(NotFound):
        await service.assign(ACTOR, "driver", 12345, RID, DRIVER.id, ip=None)


async def test_vehicle_with_a_driver_cannot_get_a_second_one() -> None:
    occupied = Vehicle(id=900, name="Bus 1", position=None, driver=DriverRef(id=2, resource_id=RID, name="Otro"))
    service, _ = _service(FakeGateway(drivers=[DRIVER], vehicles=[occupied]))

    with pytest.raises(Conflict):
        await service.assign(ACTOR, "driver", 900, RID, DRIVER.id, ip=None)


async def test_moving_a_passenger_unbinds_it_from_the_previous_vehicle_first() -> None:
    passenger = Person(id=5, resource_id=RID, name="Ana", vehicle_id=800)
    gateway = FakeGateway(passengers=[passenger], vehicles=[BUS, Vehicle(id=800, name="Bus 0", position=None)])
    service, _ = _service(gateway)

    await service.assign(ACTOR, "passenger", 900, RID, 5, ip=None)

    assert gateway.bindings == [("passenger", 5, 800, False), ("passenger", 5, 900, True)]


async def test_already_assigned_is_a_conflict() -> None:
    passenger = Person(id=5, resource_id=RID, name="Ana", vehicle_id=900)
    service, _ = _service(FakeGateway(passengers=[passenger], vehicles=[BUS]))

    with pytest.raises(Conflict):
        await service.assign(ACTOR, "passenger", 900, RID, 5, ip=None)


async def test_list_filters_by_search_and_assignment() -> None:
    people = [Person(id=1, resource_id=RID, name="Ana", vehicle_id=900), Person(id=2, resource_id=RID, name="Luis")]
    service, _ = _service(FakeGateway(passengers=people, vehicles=[BUS]))

    assigned = await service.list_people("passenger", PageRequest(), assigned=True)
    found = await service.list_people("passenger", PageRequest(), search="LUI")

    assert [v.person.id for v in assigned.items] == [1]
    assert assigned.items[0].vehicle_name == "Bus 1"
    assert [v.person.id for v in found.items] == [2]


# --------------------------------------------------- autorización (TST-02)


@pytest.mark.parametrize(
    ("role", "method", "path", "expected"),
    [
        ("viewer", "GET", "/api/v1/drivers", 200),
        ("viewer", "POST", "/api/v1/drivers", 403),
        ("viewer", "PATCH", f"/api/v1/passengers/{RID}/1", 403),
        ("viewer", "DELETE", f"/api/v1/drivers/{RID}/1", 403),
        ("viewer", "PUT", f"/api/v1/vehicles/900/drivers/{RID}/1", 403),
        ("operator", "POST", "/api/v1/passengers", 201),
        ("operator", "PUT", f"/api/v1/vehicles/900/drivers/{RID}/1", 204),
    ],
)
async def test_people_endpoints_apply_the_role_matrix(
    app: FastAPI, client: httpx.AsyncClient, role: str, method: str, path: str, expected: int
) -> None:
    app.state.fleet_gateway = FakeGateway(drivers=[DRIVER], passengers=[Person(id=1, resource_id=RID, name="Ana")], vehicles=[BUS])
    await create_user(app, f"{role}@flota.example.com", role=role)
    await login(client, f"{role}@flota.example.com")
    body = {"name": "Nuevo", "code": "N-1"} if method in ("POST", "PATCH") else None

    response = await client.request(method, path, json=body, headers=csrf_headers(client))

    assert response.status_code == expected
