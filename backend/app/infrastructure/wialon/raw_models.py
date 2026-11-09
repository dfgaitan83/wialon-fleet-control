"""Modelos Pydantic de los datos CRUDOS de Wialon, validados ANTES de mapear (SEG-08).

¿Por qué existen?
- **Nunca confiar en datos externos.** Wialon es un sistema de terceros: un GPS
  averiado puede mandar latitud 95° o velocidad negativa, y una respuesta puede
  venir incompleta. Los mappers (M4) reciben modelos ya validados, así que no
  tienen que defenderse de ``KeyError`` ni de tipos inesperados.
- **Lista blanca de campos** (``extra="ignore"``). Wialon envía secretos junto a
  los datos útiles (verificado en demoApps): ``psw`` (contraseña del equipo GPS)
  en cada unidad y ``pwd`` en cada conductor. Como esos campos NO se declaran
  aquí, se descartan al validar y ninguna capa superior puede filtrarlos.
- **Inmutables** (``frozen=True``): el dato de Wialon es una foto de solo lectura;
  para cambiar algo se crea un objeto nuevo.

Decisiones ante datos inválidos (sin tumbar la flota entera):
- Posición inválida -> ``pos=None``: el vehículo se muestra "sin posición".
- Elemento inválido (p. ej. sin ``id``) -> se descarta de la lista y se registra.
Nunca se registran los valores recibidos, solo el id y los campos que fallaron:
los mensajes de error de Pydantic incluyen el valor y podría ser un dato personal.

Nomenclatura de Wialon (abreviada) conservada a propósito: los mappers traducen
a nombres de dominio legibles; aquí se refleja el contrato real de la API.
"""

import logging
from collections.abc import Iterable
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    ValidatorFunctionWrapHandler,
    field_validator,
)

logger = logging.getLogger(__name__)


class _RawModel(BaseModel):
    """Base común: inmutable y con lista blanca de campos."""

    model_config = ConfigDict(frozen=True, extra="ignore")


# ---------------------------------------------------------------------------
# Unidades (vehículos, avl_unit)
# ---------------------------------------------------------------------------
class RawPosition(_RawModel):
    """Última posición conocida (bloque ``pos``, flag 0x400)."""

    x: float = Field(ge=-180, le=180)  # longitud en grados
    y: float = Field(ge=-90, le=90)  # latitud en grados
    s: int = Field(ge=0)  # velocidad; con mu=3 (todo demoApps) ya viene en km/h
    c: int = Field(ge=0, le=360)  # rumbo en grados (0 = norte)
    t: int = Field(ge=0)  # hora del mensaje, Unix UTC (segundos)
    z: float | None = None  # altitud en metros (llega como int o float)
    sc: int = 0  # satélites visibles


class RawCustomField(_RawModel):
    """Campo personalizado de la unidad (bloque ``flds``, flag 0x8)."""

    id: int
    n: str  # nombre del campo (ej. "Placa")
    v: str  # valor


class RawUnit(_RawModel):
    """Vehículo. Solo los campos que usa la app; ``psw``, ``ph``, ``uid``... se descartan."""

    id: int
    nm: str  # nombre visible del vehículo
    mu: int = 0  # sistema de unidades: 0 métrico, 1 EE. UU., 2 imperial, 3 métrico + galón EE. UU.
    uacl: int = 0  # máscara de permisos del token sobre esta unidad
    pos: RawPosition | None = None  # None = nunca reportó o el dato era inválido
    flds: dict[str, RawCustomField] = {}  # campos personalizados por id (Pydantic copia el default)

    @field_validator("pos", mode="wrap")
    @classmethod
    def _invalid_position_as_none(
        cls, value: Any, handler: ValidatorFunctionWrapHandler, info: ValidationInfo
    ) -> RawPosition | None:
        """Una posición basura se trata como "sin posición" en vez de descartar el vehículo."""
        try:
            return handler(value)
        except ValidationError as exc:
            fields = sorted({str(err["loc"][0]) for err in exc.errors() if err["loc"]})
            logger.warning(
                "Wialon: posición inválida en la unidad id=%s (campos: %s); se trata como sin posición",
                info.data.get("id"),
                ", ".join(fields),
            )
            return None


# ---------------------------------------------------------------------------
# Recursos (avl_resource): contenedor de conductores y pasajeros
# ---------------------------------------------------------------------------
class RawDriver(_RawModel):
    """Conductor (bloque ``drvrs``, flag 0x100). ``pwd`` NO se declara: se descarta."""

    id: int
    n: str  # nombre
    c: str = ""  # código del conductor (puede venir vacío: 14 casos reales)
    ds: str = ""  # descripción
    p: str = ""  # teléfono
    bu: int = 0  # id de la unidad asignada; 0 = sin vehículo
    jp: dict[str, str] = {}  # campos personalizados (todos str en los datos reales)


class RawPassenger(_RawModel):
    """Pasajero; Wialon los llama "tags" (bloque ``tags``, flag 0x200000).

    ``jp`` se conserva COMPLETO: al editar un pasajero hay que leer-fusionar-escribir
    para no borrar sus campos personalizados (RF-27).
    """

    id: int
    n: str  # nombre
    c: str = ""  # código
    ds: str = ""  # descripción
    p: str = ""  # teléfono
    bu: int = 0  # id de la unidad asignada; 0 = sin vehículo
    jp: dict[str, str] = {}


class RawResource(_RawModel):
    """Recurso de Wialon. En demoApps, el id 27668776 tiene 16 conductores y 102 pasajeros."""

    id: int
    nm: str
    mu: int = 0
    uacl: int = 0
    drvrs: dict[str, RawDriver] = {}  # conductores por id (Wialon usa el id como clave str)
    tags: dict[str, RawPassenger] = {}  # pasajeros por id


# ---------------------------------------------------------------------------
# Validación de listas completas
# ---------------------------------------------------------------------------
# Genéricos PEP 695 (Python 3.12+): [M: _RawModel] = "cualquier modelo crudo"; así
# parse_units devuelve list[RawUnit] y parse_resources list[RawResource] sin duplicar código.
def _try_validate[M: _RawModel](model: type[M], raw: Any, kind: str) -> M | None:
    """Valida UN elemento; si es inválido lo registra (sin sus valores) y devuelve None."""
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        item_id = raw.get("id") if isinstance(raw, dict) else None
        logger.warning(
            "Wialon: %s descartado por datos inválidos (id=%s, %s errores)",
            kind,
            item_id,
            exc.error_count(),
        )
        return None


def _parse_many[M: _RawModel](model: type[M], items: Iterable[Any], kind: str) -> list[M]:
    """Valida cada elemento por separado: uno corrupto no vacía la lista entera."""
    validated = (_try_validate(model, raw, kind) for raw in items)
    return [item for item in validated if item is not None]


def parse_units(items: Iterable[Any]) -> list[RawUnit]:
    """Valida la respuesta de ``core/search_items`` para ``avl_unit``."""
    return _parse_many(RawUnit, items, "unidad")


def parse_resources(items: Iterable[Any]) -> list[RawResource]:
    """Valida la respuesta de ``core/search_items`` para ``avl_resource``."""
    return _parse_many(RawResource, items, "recurso")
