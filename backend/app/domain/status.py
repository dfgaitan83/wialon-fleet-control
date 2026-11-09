"""Regla del estado derivado del vehículo (sección 4.4) — patrón Strategy.

Reglas documentadas (ThresholdStatusStrategy, valores por defecto):
1. Sin posición válida                          -> OFFLINE ("sin señal")
2. Último reporte hace MÁS de 30 minutos        -> OFFLINE (desconectado)
3. Reporte reciente y velocidad >= 5 km/h       -> MOVING  (en movimiento)
4. Reporte reciente y velocidad <  5 km/h       -> STOPPED (detenido)

¿Por qué 5 km/h y no 0? El GPS "deriva" unos km/h con el vehículo quieto
(ruido de la señal); con 0 un bus parqueado parpadearía entre "detenido" y
"en movimiento". ¿Por qué 30 min? Las unidades reportan cada pocos minutos;
media hora sin reportes indica equipo apagado o sin cobertura.

¿Por qué Strategy? Si negocio cambia los umbrales (o quiere otra regla, p. ej.
"en ralentí" con el motor encendido), se inyecta otra estrategia sin tocar el
servicio ni los endpoints (abierto/cerrado).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from app.domain.fleet import Position, VehicleStatus

MOVING_SPEED_KMH = 5.0
OFFLINE_AFTER = timedelta(minutes=30)


class StatusStrategy(Protocol):
    def classify(self, position: Position | None, now: datetime) -> VehicleStatus: ...


@dataclass(frozen=True)
class ThresholdStatusStrategy:
    moving_speed_kmh: float = MOVING_SPEED_KMH
    offline_after: timedelta = OFFLINE_AFTER

    def classify(self, position: Position | None, now: datetime) -> VehicleStatus:
        if position is None:
            return VehicleStatus.OFFLINE
        if now - position.recorded_at > self.offline_after:
            return VehicleStatus.OFFLINE
        if position.speed_kmh >= self.moving_speed_kmh:
            return VehicleStatus.MOVING
        return VehicleStatus.STOPPED
