"""Entidades de flota (dominio puro: solo librería estándar).

Son modelos PROPIOS (INT-04): nombres claros y tipos explícitos, sin la
nomenclatura abreviada de Wialon (``nm``, ``pos.y``, ``bu``...). La traducción
desde Wialon la hacen los mappers de ``app/infrastructure/wialon/mappers.py``.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class VehicleStatus(StrEnum):
    """Estado DERIVADO por el backend (sección 4.4). Reglas en ``status.py``."""

    MOVING = "moving"  # en movimiento
    STOPPED = "stopped"  # detenido (reporta, pero sin velocidad)
    OFFLINE = "offline"  # sin señal / desconectado (no reporta hace rato o nunca reportó)


@dataclass(frozen=True)
class Position:
    latitude: float  # grados, validados en [-90, 90]
    longitude: float  # grados, validados en [-180, 180]
    speed_kmh: float  # SIEMPRE km/h (convertido si la unidad reporta mph)
    heading_deg: int  # rumbo en grados (0 = norte); el punto cardinal lo pinta la UI
    recorded_at: datetime  # UTC
    altitude_m: float | None = None
    satellites: int = 0


@dataclass(frozen=True)
class CustomField:
    id: int
    name: str
    value: str


@dataclass(frozen=True)
class DriverRef:
    """Conductor vinculado (bindeado) a un vehículo en Wialon (RF-13)."""

    id: int
    resource_id: int  # recurso de Wialon donde vive el conductor
    name: str
    code: str = ""
    phone: str = ""


@dataclass(frozen=True)
class PassengerRef:
    id: int
    resource_id: int
    name: str
    code: str = ""


@dataclass(frozen=True)
class Vehicle:
    id: int
    name: str
    position: Position | None  # None = nunca reportó o el dato del GPS era inválido
    custom_fields: tuple[CustomField, ...] = ()
    driver: DriverRef | None = None  # None = "Sin conductor asignado"
    passengers: tuple[PassengerRef, ...] = ()


@dataclass(frozen=True)
class FleetSnapshot:
    """Foto de la flota en un instante: vehículos + totales de personas (para KPIs)."""

    vehicles: tuple[Vehicle, ...]
    total_drivers: int
    total_passengers: int
    fetched_at: datetime
