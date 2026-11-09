"""Historial de recorridos de un vehículo (RF-24).

Depende solo del puerto ``TrackGateway`` (no sabe que existe Wialon). Valida el
rango ANTES de llamar al proveedor (fail fast) y calcula las estadísticas del
recorrido aquí, no en el front: la regla queda en un solo lugar y es testeable.
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import pairwise
from typing import Protocol

from app.application.errors import ValidationFailed
from app.domain.fleet import Position

# Límite del rango: Wialon carga los mensajes en memoria de la sesión; 7 días de
# un vehículo activo son ~20-40 mil mensajes, suficiente para una consulta interactiva.
MAX_RANGE = timedelta(days=7)
# Puntos máximos enviados al navegador: más no se distinguen en el mapa y
# multiplican el peso de la respuesta. Se reduce por muestreo uniforme.
MAX_POINTS = 2000
EARTH_RADIUS_KM = 6371.0088


class TrackGateway(Protocol):
    """Puerto hacia el proveedor GPS (segregado de ``FleetGateway``: ISP)."""

    async def track(self, vehicle_id: int, start: datetime, end: datetime) -> list[Position]: ...


@dataclass(frozen=True)
class Track:
    vehicle_id: int
    start: datetime
    end: datetime
    points: tuple[Position, ...]  # orden cronológico, ya muestreados
    total_points: int  # mensajes con posición válida ANTES del muestreo
    distance_km: float
    max_speed_kmh: float
    moving_minutes: float  # tiempo entre puntos consecutivos con velocidad > 0


class HistoryService:
    def __init__(self, gateway: TrackGateway, clock: Callable[[], datetime]) -> None:
        self._gateway = gateway
        self._clock = clock

    async def track(self, vehicle_id: int, start: datetime, end: datetime) -> Track:
        _validate_range(start, end, self._clock())
        positions = sorted(await self._gateway.track(vehicle_id, start, end), key=lambda p: p.recorded_at)
        return Track(
            vehicle_id=vehicle_id,
            start=start,
            end=end,
            points=downsample(positions, MAX_POINTS),
            total_points=len(positions),
            distance_km=round(path_distance_km(positions), 2),
            max_speed_kmh=max((p.speed_kmh for p in positions), default=0.0),
            moving_minutes=round(_moving_seconds(positions) / 60, 1),
        )


def _validate_range(start: datetime, end: datetime, now: datetime) -> None:
    errors: dict[str, list[str]] = {}
    if start.tzinfo is None or end.tzinfo is None:
        errors["from"] = ["Las fechas deben incluir zona horaria (ISO-8601)."]
    elif start >= end:
        errors["from"] = ["La fecha inicial debe ser anterior a la final."]
    elif end - start > MAX_RANGE:
        errors["to"] = [f"El rango máximo es de {MAX_RANGE.days} días."]
    elif start > now:
        errors["from"] = ["La fecha inicial no puede estar en el futuro."]
    if errors:
        raise ValidationFailed("Rango de fechas inválido.", errors)


def haversine_km(a: Position, b: Position) -> float:
    """Distancia sobre la esfera terrestre entre dos posiciones (fórmula del semiverseno)."""
    lat1, lat2 = math.radians(a.latitude), math.radians(b.latitude)
    dlat = lat2 - lat1
    dlon = math.radians(b.longitude - a.longitude)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def path_distance_km(points: Sequence[Position]) -> float:
    return sum(haversine_km(a, b) for a, b in pairwise(points))


def _moving_seconds(points: Sequence[Position]) -> float:
    return sum(
        (b.recorded_at - a.recorded_at).total_seconds()
        for a, b in pairwise(points)
        if a.speed_kmh > 0
    )


def downsample(points: Sequence[Position], limit: int) -> tuple[Position, ...]:
    """Muestreo uniforme que CONSERVA el primer y el último punto (inicio y fin reales)."""
    if len(points) <= limit:
        return tuple(points)
    step = (len(points) - 1) / (limit - 1)
    return tuple(points[round(i * step)] for i in range(limit))
