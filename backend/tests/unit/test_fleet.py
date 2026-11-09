"""Tests de flota (M4/M5): estrategia de estado en los bordes, mappers con fixtures
reales, servicio (búsqueda, filtro, paginación, KPIs) y gateway (caché y errores)."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.application.errors import NotFound, ProviderUnavailable
from app.application.fleet_service import FleetService
from app.application.pagination import PageRequest
from app.domain.fleet import FleetSnapshot, Position, Vehicle, VehicleStatus
from app.domain.status import ThresholdStatusStrategy
from app.infrastructure.wialon.errors import WialonUnavailable
from app.infrastructure.wialon.gateway import WialonFleetGateway
from app.infrastructure.wialon.mappers import KMH_PER_MPH, build_snapshot, to_position
from app.infrastructure.wialon.raw_models import (
    RawPosition,
    parse_resources,
    parse_units,
)

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "wialon"


def _position(speed: float = 0, minutes_ago: float = 1) -> Position:
    return Position(
        latitude=4.6, longitude=-74.08, speed_kmh=speed, heading_deg=90,
        recorded_at=NOW - timedelta(minutes=minutes_ago),
    )


# --------------------------------------------- estrategia de estado (bordes)


@pytest.mark.parametrize(
    ("speed", "minutes_ago", "expected"),
    [
        (4.9, 1, VehicleStatus.STOPPED),  # justo debajo del umbral de movimiento
        (5.0, 1, VehicleStatus.MOVING),  # el umbral cuenta como movimiento
        (60, 29, VehicleStatus.MOVING),  # reporte reciente
        (60, 31, VehicleStatus.OFFLINE),  # más de 30 min sin reportar
        (0, 31, VehicleStatus.OFFLINE),
    ],
)
def test_threshold_strategy_edges(speed: float, minutes_ago: float, expected: VehicleStatus) -> None:
    assert ThresholdStatusStrategy().classify(_position(speed, minutes_ago), NOW) == expected


def test_vehicle_without_position_is_offline() -> None:
    assert ThresholdStatusStrategy().classify(None, NOW) == VehicleStatus.OFFLINE


# ------------------------------------------------------- mappers (fixtures)


def _real_snapshot() -> FleetSnapshot:
    units = parse_units(json.loads((FIXTURES / "units.json").read_text(encoding="utf-8")))
    resources = parse_resources(json.loads((FIXTURES / "resources.json").read_text(encoding="utf-8")))
    return build_snapshot(units, resources, NOW)


def test_real_fixtures_map_to_domain_vehicles() -> None:
    snapshot = _real_snapshot()

    assert len(snapshot.vehicles) == 62
    assert sum(1 for v in snapshot.vehicles if v.position is None) == 1  # sin posición: no rompe
    assert (snapshot.total_drivers, snapshot.total_passengers) == (16, 102)
    assert all(v.position.recorded_at.tzinfo is UTC for v in snapshot.vehicles if v.position)


def test_driver_is_linked_through_its_bound_unit() -> None:
    snapshot = _real_snapshot()

    with_driver = [v for v in snapshot.vehicles if v.driver is not None]

    assert with_driver  # hay conductores vinculados en los datos reales
    assert all(v.driver.resource_id > 0 for v in with_driver)


def test_speed_in_mph_is_converted_to_kmh() -> None:
    raw = RawPosition(x=-74.0, y=4.6, s=10, c=0, t=1_700_000_000)

    assert to_position(raw, measure_units=1).speed_kmh == round(10 * KMH_PER_MPH, 1)
    assert to_position(raw, measure_units=3).speed_kmh == 10.0  # métrico: sin conversión


# ------------------------------------------------------------- servicio


class FakeGateway:
    def __init__(self, vehicles: list[Vehicle]) -> None:
        self._snapshot = FleetSnapshot(tuple(vehicles), total_drivers=3, total_passengers=7, fetched_at=NOW)

    async def snapshot(self) -> FleetSnapshot:
        return self._snapshot


def _service(*vehicles: Vehicle) -> FleetService:
    return FleetService(FakeGateway(list(vehicles)), ThresholdStatusStrategy(), clock=lambda: NOW)


VEHICLES = (
    Vehicle(id=1, name="Bus Norte", position=_position(speed=40)),
    Vehicle(id=2, name="Bus Sur", position=_position(speed=0)),
    Vehicle(id=3, name="Camión", position=None),
)


async def test_list_filters_by_status_and_searches() -> None:
    service = _service(*VEHICLES)

    moving = await service.list_vehicles(PageRequest(), status=VehicleStatus.MOVING)
    search = await service.list_vehicles(PageRequest(), search="  BUS ")

    assert [v.vehicle.id for v in moving.items] == [1]
    assert {v.vehicle.id for v in search.items} == {1, 2}


async def test_list_is_paginated_on_the_server() -> None:
    page = await _service(*VEHICLES).list_vehicles(PageRequest(page=2, page_size=2))

    assert (page.total, len(page.items)) == (3, 1)


async def test_summary_counts_states_and_drivers() -> None:
    summary = await _service(*VEHICLES).summary()

    assert summary.total_vehicles == 3
    assert summary.by_status == {VehicleStatus.MOVING: 1, VehicleStatus.STOPPED: 1, VehicleStatus.OFFLINE: 1}
    assert (summary.with_driver, summary.without_driver) == (0, 3)


async def test_unknown_vehicle_is_not_found() -> None:
    with pytest.raises(NotFound):
        await _service(*VEHICLES).get_vehicle(999)


# -------------------------------------------------------------- gateway


class FakeClient:
    def __init__(self, fail: bool = False) -> None:
        self.calls = 0
        self._fail = fail

    async def search_items(self, items_type: str, flags: int) -> list[dict]:
        self.calls += 1
        if self._fail:
            raise WialonUnavailable(-1, "sin red")
        return [{"id": 1, "nm": "Bus 1"}] if items_type == "avl_unit" else []


async def test_gateway_caches_the_snapshot() -> None:
    client = FakeClient()
    gateway = WialonFleetGateway(client, clock=lambda: NOW)  # type: ignore[arg-type]

    await gateway.snapshot()
    await gateway.snapshot()

    assert client.calls == 2  # 1 unidades + 1 recursos: la segunda lectura vino de la caché


async def test_gateway_translates_wialon_errors_to_provider_unavailable() -> None:
    gateway = WialonFleetGateway(FakeClient(fail=True), clock=lambda: NOW)  # type: ignore[arg-type]

    with pytest.raises(ProviderUnavailable):
        await gateway.snapshot()
