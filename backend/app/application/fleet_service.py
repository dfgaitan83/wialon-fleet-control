"""Casos de uso de lectura de flota: vehículos, posiciones y KPIs (RF-10..13, RF-23).

Depende solo del puerto ``FleetGateway`` (no sabe que existe Wialon) y de la
estrategia de estado (patrón Strategy, ``app/domain/status.py``).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.application.errors import NotFound
from app.application.pagination import Page, PageRequest
from app.domain.fleet import FleetSnapshot, Vehicle, VehicleStatus
from app.domain.status import StatusStrategy


class FleetGateway(Protocol):
    """Puerto hacia el proveedor GPS. Lanza ``ProviderUnavailable`` si no responde."""

    async def snapshot(self) -> FleetSnapshot: ...


@dataclass(frozen=True)
class VehicleView:
    """Vehículo + estado derivado en el instante de la consulta."""

    vehicle: Vehicle
    status: VehicleStatus


@dataclass(frozen=True)
class FleetSummary:
    total_vehicles: int
    by_status: dict[VehicleStatus, int]
    with_driver: int
    without_driver: int
    total_drivers: int
    total_passengers: int
    generated_at: datetime


class FleetService:
    def __init__(
        self, gateway: FleetGateway, strategy: StatusStrategy, clock: Callable[[], datetime]
    ) -> None:
        self._gateway = gateway
        self._strategy = strategy
        self._clock = clock

    async def _views(self) -> list[VehicleView]:
        snapshot = await self._gateway.snapshot()
        now = self._clock()
        return [VehicleView(v, self._strategy.classify(v.position, now)) for v in snapshot.vehicles]

    async def list_vehicles(
        self, request: PageRequest, *, search: str | None = None, status: VehicleStatus | None = None
    ) -> Page[VehicleView]:
        """Búsqueda por nombre/conductor + filtro por estado + paginación del servidor (RF-10)."""
        term = search.strip().lower() if search and search.strip() else None
        views = [
            view
            for view in await self._views()
            if (status is None or view.status == status) and (term is None or _matches(view.vehicle, term))
        ]
        views.sort(key=lambda view: view.vehicle.name.lower())  # orden estable y legible
        start = request.offset
        return Page(
            items=views[start : start + request.page_size],
            total=len(views),
            page=request.page,
            page_size=request.page_size,
        )

    async def positions(self) -> list[VehicleView]:
        """Todos los vehículos CON posición, para el mapa (endpoint liviano)."""
        return [view for view in await self._views() if view.vehicle.position is not None]

    async def get_vehicle(self, vehicle_id: int) -> VehicleView:
        for view in await self._views():
            if view.vehicle.id == vehicle_id:
                return view
        raise NotFound("El vehículo no existe o no es visible para esta cuenta.")

    async def summary(self) -> FleetSummary:
        """KPIs del dashboard (RF-23), calculados sobre la MISMA foto que la lista."""
        snapshot = await self._gateway.snapshot()
        now = self._clock()
        counts = dict.fromkeys(VehicleStatus, 0)
        for vehicle in snapshot.vehicles:
            counts[self._strategy.classify(vehicle.position, now)] += 1
        with_driver = sum(1 for v in snapshot.vehicles if v.driver is not None)
        return FleetSummary(
            total_vehicles=len(snapshot.vehicles),
            by_status=counts,
            with_driver=with_driver,
            without_driver=len(snapshot.vehicles) - with_driver,
            total_drivers=snapshot.total_drivers,
            total_passengers=snapshot.total_passengers,
            generated_at=now,
        )


def _matches(vehicle: Vehicle, term: str) -> bool:
    driver_name = vehicle.driver.name.lower() if vehicle.driver else ""
    return term in vehicle.name.lower() or term in driver_name
