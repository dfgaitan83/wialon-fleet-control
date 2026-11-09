"""Endpoints de flota: /api/v1/vehicles*, /dashboard/summary e historial (RF-10..13, RF-23, RF-24)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import FleetServiceDep, HistoryServiceDep, require_permission
from app.api.v1.fleet_schemas import (
    DashboardSummaryOut,
    TrackOut,
    VehicleDetailOut,
    VehicleOut,
    VehiclePositionOut,
)
from app.api.v1.schemas import PageOut
from app.application.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, PageRequest
from app.domain.fleet import VehicleStatus
from app.domain.permissions import Permission
from app.domain.users import User

_PROBLEM = {"model": None, "content": {"application/problem+json": {}}}

VehiclesReader = Annotated[User, Depends(require_permission(Permission.VEHICLES_READ))]
HistoryReader = Annotated[User, Depends(require_permission(Permission.HISTORY_READ))]
DashboardReader = Annotated[User, Depends(require_permission(Permission.DASHBOARD_READ))]

router = APIRouter(tags=["fleet"], responses={401: _PROBLEM, 403: _PROBLEM, 503: _PROBLEM})


@router.get("/vehicles", response_model=PageOut[VehicleOut], summary="Vehículos con estado derivado (paginado)")
async def list_vehicles(
    _user: VehiclesReader,
    service: FleetServiceDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    q: Annotated[str | None, Query(max_length=100, description="Busca en vehículo y conductor")] = None,
    status: Annotated[VehicleStatus | None, Query(description="moving | stopped | offline")] = None,
) -> PageOut[VehicleOut]:
    result = await service.list_vehicles(PageRequest(page=page, page_size=page_size), search=q, status=status)
    return PageOut(
        items=[VehicleOut.from_view(v) for v in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get(
    "/vehicles/positions",
    response_model=list[VehiclePositionOut],
    summary="Posiciones actuales (liviano, para el mapa y el polling)",
)
async def vehicle_positions(_user: VehiclesReader, service: FleetServiceDep) -> list[VehiclePositionOut]:
    return [VehiclePositionOut.from_view(v) for v in await service.positions()]


@router.get(
    "/vehicles/{vehicle_id}",
    response_model=VehicleDetailOut,
    responses={404: _PROBLEM},
    summary="Detalle: posición, estado, conductor, pasajeros y campos personalizados",
)
async def get_vehicle(vehicle_id: int, _user: VehiclesReader, service: FleetServiceDep) -> VehicleDetailOut:
    return VehicleDetailOut.from_detail(await service.get_vehicle(vehicle_id))


@router.get("/dashboard/summary", response_model=DashboardSummaryOut, summary="KPIs del dashboard (RF-23)")
async def dashboard_summary(_user: DashboardReader, service: FleetServiceDep) -> DashboardSummaryOut:
    return DashboardSummaryOut.from_summary(await service.summary())


@router.get(
    "/vehicles/{vehicle_id}/track",
    response_model=TrackOut,
    responses={404: _PROBLEM, 422: _PROBLEM},
    summary="Historial de recorrido en un rango (máx. 7 días) para el playback (RF-24)",
)
async def vehicle_track(
    vehicle_id: int,
    _user: HistoryReader,
    service: HistoryServiceDep,
    start: Annotated[datetime, Query(alias="from", description="ISO-8601 con zona, p. ej. 2026-11-08T05:00:00Z")],
    end: Annotated[datetime, Query(alias="to", description="ISO-8601 con zona")],
) -> TrackOut:
    return TrackOut.from_track(await service.track(vehicle_id, start, end))
