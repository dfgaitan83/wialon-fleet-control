"""Mappers: modelos crudos VALIDADOS de Wialon -> entidades de dominio (patrón DTO/Mapper).

Transformaciones (sección 4.4):
- ``pos.y`` / ``pos.x`` -> latitude / longitude (ya validadas en raw_models).
- ``pos.s`` -> speed_kmh: con ``mu`` 1 o 2 (EE. UU. / imperial) Wialon reporta mph y
  se convierte; con 0 o 3 (métrico) ya viene en km/h. En demoApps todo es mu=3.
- ``pos.t`` (Unix) -> datetime UTC (la API la expone en ISO-8601).
- Conductor del vehículo: el conductor cuyo ``bu`` (unidad vinculada) es el id del
  vehículo (RF-13). Pasajeros: todos los tags con ese ``bu``.
"""

from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime

from app.domain.fleet import (
    CustomField,
    DriverRef,
    FleetSnapshot,
    PassengerRef,
    Position,
    Vehicle,
)
from app.infrastructure.wialon.raw_models import RawPosition, RawResource, RawUnit

KMH_PER_MPH = 1.609344
MPH_MEASURE_UNITS = frozenset({1, 2})  # 1 = EE. UU., 2 = imperial
NO_UNIT = 0  # bu = 0 -> conductor/pasajero sin vehículo


def to_position(raw: RawPosition | None, measure_units: int) -> Position | None:
    if raw is None:
        return None
    speed = raw.s * KMH_PER_MPH if measure_units in MPH_MEASURE_UNITS else float(raw.s)
    return Position(
        latitude=raw.y,
        longitude=raw.x,
        speed_kmh=round(speed, 1),
        heading_deg=raw.c,
        recorded_at=datetime.fromtimestamp(raw.t, tz=UTC),
        altitude_m=raw.z,
        satellites=raw.sc,
    )


def _drivers_by_unit(resources: Iterable[RawResource]) -> dict[int, DriverRef]:
    bound: dict[int, DriverRef] = {}
    for resource in resources:
        for driver in sorted(resource.drvrs.values(), key=lambda d: d.id):  # orden determinista
            if driver.bu != NO_UNIT:
                bound.setdefault(
                    driver.bu,
                    DriverRef(id=driver.id, resource_id=resource.id, name=driver.n, code=driver.c, phone=driver.p),
                )
    return bound


def _passengers_by_unit(resources: Iterable[RawResource]) -> dict[int, list[PassengerRef]]:
    bound: dict[int, list[PassengerRef]] = defaultdict(list)
    for resource in resources:
        for tag in resource.tags.values():
            if tag.bu != NO_UNIT:
                bound[tag.bu].append(PassengerRef(id=tag.id, resource_id=resource.id, name=tag.n, code=tag.c))
    return bound


def to_vehicle(
    unit: RawUnit, driver: DriverRef | None = None, passengers: Iterable[PassengerRef] = ()
) -> Vehicle:
    fields = sorted(unit.flds.values(), key=lambda f: f.id)
    return Vehicle(
        id=unit.id,
        name=unit.nm,
        position=to_position(unit.pos, unit.mu),
        custom_fields=tuple(CustomField(id=f.id, name=f.n, value=f.v) for f in fields),
        driver=driver,
        passengers=tuple(sorted(passengers, key=lambda p: p.name.lower())),
    )


def build_snapshot(units: list[RawUnit], resources: list[RawResource], fetched_at: datetime) -> FleetSnapshot:
    drivers = _drivers_by_unit(resources)
    passengers = _passengers_by_unit(resources)
    return FleetSnapshot(
        vehicles=tuple(to_vehicle(u, drivers.get(u.id), passengers.get(u.id, ())) for u in units),
        total_drivers=sum(len(r.drvrs) for r in resources),
        total_passengers=sum(len(r.tags) for r in resources),
        fetched_at=fetched_at,
    )
