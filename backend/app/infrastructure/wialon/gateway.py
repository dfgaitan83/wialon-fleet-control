"""Gateway Wialon: implementa el puerto ``FleetGateway`` (patrón Adapter, INT-03).

- Pide unidades y recursos, VALIDA los datos crudos (raw_models, SEG-08) y los
  mapea a entidades de dominio (mappers).
- Caché TTL de 15 s (INT-06): el polling del mapa de N usuarios no multiplica las
  llamadas a Wialon. Un ``asyncio.Lock`` evita la "estampida": si la caché expira
  y llegan 20 peticiones, solo UNA va a Wialon y las demás reciben su resultado.
- Traduce los errores de Wialon a ``ProviderUnavailable`` (503): ninguna capa
  superior conoce ``WialonError`` (regla hexagonal).
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime

from cachetools import TTLCache

from app.application.errors import ProviderUnavailable
from app.domain.fleet import FleetSnapshot, Person, PersonChanges, PersonKind
from app.infrastructure.wialon.client import (
    RESOURCE_FLAG_BASE,
    RESOURCE_FLAG_DRIVERS,
    RESOURCE_FLAG_TAGS,
    UNIT_FLAG_BASE,
    UNIT_FLAG_CUSTOM_FIELDS,
    UNIT_FLAG_LAST_MESSAGE_POSITION,
    WialonClient,
)
from app.infrastructure.wialon.errors import WialonError
from app.infrastructure.wialon.mappers import build_snapshot
from app.infrastructure.wialon.people_writer import WialonPeopleWriter
from app.infrastructure.wialon.raw_models import parse_resources, parse_units

logger = logging.getLogger(__name__)

SNAPSHOT_TTL_SECONDS = 15.0
# Solo los bloques que usa la app (menos datos = respuesta más rápida y menos exposición).
UNIT_FLAGS_FLEET = UNIT_FLAG_BASE + UNIT_FLAG_CUSTOM_FIELDS + UNIT_FLAG_LAST_MESSAGE_POSITION  # 1033
RESOURCE_FLAGS_PEOPLE = RESOURCE_FLAG_BASE + RESOURCE_FLAG_DRIVERS + RESOURCE_FLAG_TAGS  # 2097409
_KEY = "snapshot"


class WialonFleetGateway:
    def __init__(
        self, client: WialonClient, clock: Callable[[], datetime], ttl_seconds: float = SNAPSHOT_TTL_SECONDS
    ) -> None:
        self._client = client
        self._writer = WialonPeopleWriter(client)
        self._clock = clock
        self._cache: TTLCache[str, FleetSnapshot] = TTLCache(maxsize=1, ttl=ttl_seconds)
        self._lock = asyncio.Lock()

    async def snapshot(self) -> FleetSnapshot:
        cached = self._cache.get(_KEY)
        if cached is not None:
            return cached
        async with self._lock:
            cached = self._cache.get(_KEY)  # otra tarea pudo llenarla mientras esperábamos
            if cached is not None:
                return cached
            fresh = await self._fetch()
            self._cache[_KEY] = fresh
            return fresh

    def invalidate(self) -> None:
        """Tras una escritura en Wialon: la próxima lectura trae datos frescos."""
        self._cache.clear()

    # --- Escrituras de personas (mismo candado: Wialon no admite peticiones paralelas) ---
    async def create_person(self, kind: PersonKind, resource_id: int, data: PersonChanges) -> Person:
        async with self._lock:
            person = await self._writer.create(kind, resource_id, data)
            self.invalidate()
            return person

    async def update_person(
        self, kind: PersonKind, resource_id: int, person_id: int, changes: PersonChanges
    ) -> Person:
        async with self._lock:
            person = await self._writer.update(kind, resource_id, person_id, changes)
            self.invalidate()
            return person

    async def delete_person(self, kind: PersonKind, resource_id: int, person_id: int) -> None:
        async with self._lock:
            await self._writer.delete(kind, resource_id, person_id)
            self.invalidate()

    async def set_person_binding(
        self, kind: PersonKind, resource_id: int, person_id: int, unit_id: int, *, bind: bool
    ) -> None:
        async with self._lock:
            await self._writer.set_binding(kind, resource_id, person_id, unit_id, bind=bind)
            self.invalidate()

    async def _fetch(self) -> FleetSnapshot:
        try:
            # Secuencial a propósito: Wialon rechaza peticiones paralelas en la misma sesión (1003).
            units = await self._client.search_items("avl_unit", UNIT_FLAGS_FLEET)
            resources = await self._client.search_items("avl_resource", RESOURCE_FLAGS_PEOPLE)
        except WialonError as exc:
            logger.warning("No se pudo leer la flota de Wialon: código %s", exc.code)
            raise ProviderUnavailable from exc
        return build_snapshot(parse_units(units), parse_resources(resources), self._clock())
