"""Entidades de flota (dominio puro: solo librería estándar).

Son modelos PROPIOS (INT-04): nombres claros y tipos explícitos, sin la
nomenclatura abreviada de Wialon (``nm``, ``pos.y``, ``bu``...). La traducción
desde Wialon la hacen los mappers de ``app/infrastructure/wialon/mappers.py``.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Literal

PersonKind = Literal["driver", "passenger"]  # conductor | pasajero ("tag" en Wialon)


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
class Person:
    """Conductor o pasajero de Wialon (ambos viven DENTRO de un recurso)."""

    id: int
    resource_id: int
    name: str
    code: str = ""
    description: str = ""
    phone: str = ""
    custom_fields: dict[str, str] = field(default_factory=dict)  # "jp" en Wialon
    vehicle_id: int | None = None  # unidad vinculada (bu); None = sin vehículo


@dataclass(frozen=True)
class PersonChanges:
    """Cambios PARCIALES: None = no tocar. El adaptador fusiona con el valor actual
    (Wialon BORRA lo que no se reenvía; verificado: omitir jp vacía los campos)."""

    name: str | None = None
    code: str | None = None
    description: str | None = None
    phone: str | None = None
    custom_fields: dict[str, str] | None = None  # si se envía, REEMPLAZA el conjunto completo


@dataclass(frozen=True)
class FleetSnapshot:
    """Foto de la flota en un instante: vehículos, conductores y pasajeros."""

    vehicles: tuple[Vehicle, ...]
    total_drivers: int
    total_passengers: int
    fetched_at: datetime
    drivers: tuple[Person, ...] = ()
    passengers: tuple[Person, ...] = ()
    people_resource_id: int | None = None  # recurso donde se crean conductores/pasajeros nuevos
