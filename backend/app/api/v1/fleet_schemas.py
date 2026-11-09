"""DTOs públicos de flota (INT-04: nunca el JSON crudo de Wialon).

Convenciones (sección 4.4): snake_case en toda la API, fechas ISO-8601 en UTC,
velocidad en km/h, rumbo en grados (el punto cardinal lo pinta la UI) y campos
opcionales explícitos (``null`` en vez de ausentes).
"""

from datetime import datetime

from pydantic import BaseModel

from app.application.fleet_service import FleetSummary, VehicleView
from app.application.history_service import Track
from app.domain.fleet import Position, VehicleStatus


class PositionOut(BaseModel):
    latitude: float
    longitude: float
    speed_kmh: float
    heading_deg: int
    recorded_at: datetime  # ISO-8601 UTC, p. ej. "2026-11-08T23:40:00Z"
    altitude_m: float | None
    satellites: int

    @classmethod
    def from_domain(cls, position: Position) -> "PositionOut":
        return cls(**position.__dict__)


class DriverOut(BaseModel):
    id: int
    resource_id: int
    name: str
    code: str
    phone: str


class PassengerOut(BaseModel):
    id: int
    resource_id: int
    name: str
    code: str


class CustomFieldOut(BaseModel):
    id: int
    name: str
    value: str


class VehicleOut(BaseModel):
    """Fila de la lista de vehículos."""

    id: int
    name: str
    status: VehicleStatus
    position: PositionOut | None
    driver: DriverOut | None  # null = "Sin conductor asignado" (RF-13)
    passenger_count: int

    @classmethod
    def from_view(cls, view: VehicleView) -> "VehicleOut":
        v = view.vehicle
        return cls(
            id=v.id,
            name=v.name,
            status=view.status,
            position=PositionOut.from_domain(v.position) if v.position else None,
            driver=DriverOut(**v.driver.__dict__) if v.driver else None,
            passenger_count=len(v.passengers),
        )


class VehiclePositionOut(BaseModel):
    """Versión LIVIANA para el mapa y el polling cada 15 s."""

    id: int
    name: str
    status: VehicleStatus
    latitude: float
    longitude: float
    speed_kmh: float
    heading_deg: int
    recorded_at: datetime
    driver_name: str | None

    @classmethod
    def from_view(cls, view: VehicleView) -> "VehiclePositionOut":
        v, p = view.vehicle, view.vehicle.position
        assert p is not None  # el servicio solo entrega vehículos con posición
        return cls(
            id=v.id, name=v.name, status=view.status, latitude=p.latitude, longitude=p.longitude,
            speed_kmh=p.speed_kmh, heading_deg=p.heading_deg, recorded_at=p.recorded_at,
            driver_name=v.driver.name if v.driver else None,
        )


class VehicleDetailOut(VehicleOut):
    passengers: list[PassengerOut]
    custom_fields: list[CustomFieldOut]

    @classmethod
    def from_detail(cls, view: VehicleView) -> "VehicleDetailOut":
        base = VehicleOut.from_view(view).model_dump()
        return cls(
            **base,
            passengers=[PassengerOut(**p.__dict__) for p in view.vehicle.passengers],
            custom_fields=[CustomFieldOut(**f.__dict__) for f in view.vehicle.custom_fields],
        )


class StatusCountOut(BaseModel):
    status: VehicleStatus
    count: int


class DashboardSummaryOut(BaseModel):
    total_vehicles: int
    by_status: list[StatusCountOut]
    with_driver: int
    without_driver: int
    total_drivers: int
    total_passengers: int
    generated_at: datetime

    @classmethod
    def from_summary(cls, s: FleetSummary) -> "DashboardSummaryOut":
        return cls(
            total_vehicles=s.total_vehicles,
            by_status=[StatusCountOut(status=k, count=v) for k, v in s.by_status.items()],
            with_driver=s.with_driver,
            without_driver=s.without_driver,
            total_drivers=s.total_drivers,
            total_passengers=s.total_passengers,
            generated_at=s.generated_at,
        )


class TrackPointOut(BaseModel):
    """Punto del recorrido (versión compacta: se envían hasta 2000)."""

    latitude: float
    longitude: float
    speed_kmh: float
    heading_deg: int
    recorded_at: datetime


class TrackOut(BaseModel):
    """Recorrido de un vehículo en un rango (RF-24). Estadísticas calculadas en backend."""

    vehicle_id: int
    start: datetime
    end: datetime
    total_points: int  # mensajes válidos en Wialon (antes del muestreo)
    distance_km: float
    max_speed_kmh: float
    moving_minutes: float
    points: list[TrackPointOut]

    @classmethod
    def from_track(cls, t: Track) -> "TrackOut":
        return cls(
            vehicle_id=t.vehicle_id, start=t.start, end=t.end, total_points=t.total_points,
            distance_km=t.distance_km, max_speed_kmh=t.max_speed_kmh, moving_minutes=t.moving_minutes,
            points=[
                TrackPointOut(
                    latitude=p.latitude, longitude=p.longitude, speed_kmh=p.speed_kmh,
                    heading_deg=p.heading_deg, recorded_at=p.recorded_at,
                )
                for p in t.points
            ],
        )
