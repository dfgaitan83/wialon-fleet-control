"""Escrituras de conductores y pasajeros en Wialon (RF-08, RF-09, RF-16, RF-17, RF-27).

Comportamiento de la API VERIFICADO en vivo contra demoApps (no supuesto):
- ``resource/update_driver`` / ``resource/update_tag`` con callMode create -> ``[id, objeto]``.
- update EXIGE ``n, c, ds, p`` y, si se omite ``jp``, Wialon BORRA los campos
  personalizados. Por eso todo update es LEER (fresco, sin caché) -> FUSIONAR -> ESCRIBIR.
- Vincular: ``bind_unit_driver`` / ``bind_unit_tag`` con ``time: 0`` y ``mode: true``.
  Desvincular: el MISMO ``unitId`` con ``mode: false`` (``unitId: 0`` no funciona).
  El vínculo de un conductor tarda ~1-2 s en reflejarse en las lecturas.

Conductor y pasajero difieren solo en nombres de servicio/bloque: una tabla de
configuración por tipo evita duplicar el código (DRY, abierto/cerrado).
"""

from dataclasses import dataclass
from typing import Any

from app.application.errors import (
    Conflict,
    NotFound,
    PermissionDenied,
    ProviderUnavailable,
)
from app.domain.fleet import Person, PersonChanges, PersonKind
from app.infrastructure.wialon.client import WialonClient
from app.infrastructure.wialon.errors import (
    WialonAccessDenied,
    WialonConflict,
    WialonError,
    WialonNotFound,
)
from app.infrastructure.wialon.mappers import to_person
from app.infrastructure.wialon.raw_models import RawDriver, RawPassenger


@dataclass(frozen=True)
class _KindConfig:
    update_svc: str
    bind_svc: str
    block: str  # bloque del recurso donde viven ("drvrs" / "tags")
    id_param: str  # nombre del id en el servicio de vínculo
    flag: int  # flag de search_item para traer ese bloque
    model: type[RawDriver] | type[RawPassenger]


_KINDS: dict[PersonKind, _KindConfig] = {
    "driver": _KindConfig("resource/update_driver", "resource/bind_unit_driver", "drvrs", "driverId", 256, RawDriver),
    "passenger": _KindConfig(
        "resource/update_tag", "resource/bind_unit_tag", "tags", "tagId", 2097152, RawPassenger
    ),
}
_RESOURCE_BASE_FLAG = 1


def _translate(exc: WialonError) -> Exception:
    """Errores de Wialon -> errores de la aplicación (nadie fuera de aquí ve WialonError)."""
    if isinstance(exc, WialonAccessDenied):
        return PermissionDenied("La cuenta de Wialon no permite modificar este recurso.")
    if isinstance(exc, WialonConflict):
        return Conflict("Wialon ya tiene un registro con ese teléfono o código. Usa otro valor.")
    if isinstance(exc, WialonNotFound):
        return NotFound("El conductor o pasajero no existe en Wialon.")
    return ProviderUnavailable()


class WialonPeopleWriter:
    def __init__(self, client: WialonClient) -> None:
        self._client = client

    async def _call(self, svc: str, params: dict[str, Any]) -> Any:
        try:
            return await self._client.call(svc, params)
        except WialonError as exc:
            raise _translate(exc) from exc

    async def read(self, kind: PersonKind, resource_id: int, person_id: int) -> Person:
        """Lectura FRESCA (sin caché) del registro actual: base del leer-fusionar-escribir."""
        cfg = _KINDS[kind]
        try:
            resource = await self._client.search_item(resource_id, _RESOURCE_BASE_FLAG + cfg.flag)
        except WialonError as exc:
            raise _translate(exc) from exc
        raw = (resource.get(cfg.block) or {}).get(str(person_id))
        if raw is None:
            raise NotFound("El conductor o pasajero no existe en Wialon.")
        return to_person(cfg.model.model_validate(raw), resource_id)

    async def create(self, kind: PersonKind, resource_id: int, data: PersonChanges) -> Person:
        cfg = _KINDS[kind]
        result = await self._call(cfg.update_svc, {
            "itemId": resource_id, "id": 0, "callMode": "create",
            "n": data.name or "", "c": data.code or "", "ds": data.description or "", "p": data.phone or "",
            "jp": data.custom_fields or {},
        })
        return to_person(cfg.model.model_validate(result[1]), resource_id)

    async def update(self, kind: PersonKind, resource_id: int, person_id: int, changes: PersonChanges) -> Person:
        current = await self.read(kind, resource_id, person_id)
        # FUSIÓN: lo no enviado conserva su valor actual (incluido jp: si no, Wialon lo borra).
        merged = {
            "n": changes.name if changes.name is not None else current.name,
            "c": changes.code if changes.code is not None else current.code,
            "ds": changes.description if changes.description is not None else current.description,
            "p": changes.phone if changes.phone is not None else current.phone,
            "jp": changes.custom_fields if changes.custom_fields is not None else current.custom_fields,
        }
        result = await self._call(
            _KINDS[kind].update_svc,
            {"itemId": resource_id, "id": person_id, "callMode": "update", **merged},
        )
        updated = to_person(_KINDS[kind].model.model_validate(result[1]), resource_id)
        return Person(**{**updated.__dict__, "vehicle_id": current.vehicle_id})  # el update no toca el vínculo

    async def delete(self, kind: PersonKind, resource_id: int, person_id: int) -> None:
        await self.read(kind, resource_id, person_id)  # 404 claro si ya no existe
        await self._call(_KINDS[kind].update_svc, {"itemId": resource_id, "id": person_id, "callMode": "delete"})

    async def set_binding(
        self, kind: PersonKind, resource_id: int, person_id: int, unit_id: int, *, bind: bool
    ) -> None:
        cfg = _KINDS[kind]
        await self._call(cfg.bind_svc, {
            "resourceId": resource_id, cfg.id_param: person_id, "unitId": unit_id, "time": 0, "mode": bind,
        })
