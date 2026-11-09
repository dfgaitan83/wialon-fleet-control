"""Tests de los modelos crudos de Wialon (``raw_models.py``, SEG-08). Sin red.

Se validan contra las fixtures REALES (enmascaradas) de demoApps: si Wialon
cambia la forma de sus datos, estos tests lo detectan antes que los mappers.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.infrastructure.wialon.raw_models import (
    RawPosition,
    RawUnit,
    parse_resources,
    parse_units,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "wialon"
RESOURCE_WITH_PEOPLE_ID = 27668776  # recurso de demoApps con conductores y pasajeros


def _load(name: str) -> Any:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _unit(**overrides: Any) -> dict[str, Any]:
    """Unidad mínima válida con la forma real de Wialon (valores ficticios)."""
    base = {
        "id": 1,
        "nm": "Bus 1",
        "mu": 3,
        "uacl": 1,
        "pos": {"x": -74.08, "y": 4.6, "s": 30, "c": 90, "t": 1_700_000_000, "z": 2600, "sc": 0},
        "flds": {"1": {"id": 1, "n": "Placa", "v": "ABC123", "ct": 1, "mt": 1}},
    }
    return {**base, **overrides}


# ---------------- Datos reales de demoApps ----------------


def test_all_real_units_validate() -> None:
    units = parse_units(_load("units"))

    assert len(units) == 62  # ninguno descartado
    assert sum(1 for u in units if u.pos is None) == 1  # el único vehículo con pos: null


def test_real_resource_exposes_drivers_and_passengers() -> None:
    resources = {r.id: r for r in parse_resources(_load("resources"))}

    people = resources[RESOURCE_WITH_PEOPLE_ID]
    assert len(people.drvrs) == 16
    assert len(people.tags) == 102  # Wialon llama "tags" a los pasajeros


def test_real_people_keep_their_jp_intact() -> None:
    # RF-27: el pasajero debe conservar TODO su jp para el leer-fusionar-escribir de M4.
    raw = _load("resources")
    raw_tag = next(iter(next(r for r in raw if r["tags"])["tags"].values()))

    tag = next(iter(parse_resources(raw)[0].tags.values()))

    assert tag.jp == raw_tag["jp"]


# ---------------- Lista blanca: los secretos no pasan ----------------


def test_unit_secrets_never_reach_the_model() -> None:
    raw = _load("units")[0]
    assert "psw" in raw  # Wialon SÍ envía la contraseña del dispositivo...

    dumped = parse_units([raw])[0].model_dump()

    assert "psw" not in dumped  # ...pero el modelo no la conserva
    assert set(dumped) == {"id", "nm", "mu", "uacl", "pos", "flds"}


def test_driver_password_never_reaches_the_model() -> None:
    resource = next(r for r in parse_resources(_load("resources")) if r.drvrs)

    driver = next(iter(resource.drvrs.values())).model_dump()

    assert "pwd" not in driver


# ---------------- Validación (SEG-08) ----------------


@pytest.mark.parametrize(
    "bad_pos",
    [
        {"x": -74.0, "y": 95.0, "s": 0, "c": 0, "t": 1},  # latitud fuera de [-90, 90]
        {"x": 200.0, "y": 4.6, "s": 0, "c": 0, "t": 1},  # longitud fuera de [-180, 180]
        {"x": -74.0, "y": 4.6, "s": -5, "c": 0, "t": 1},  # velocidad negativa
        {"x": "no-es-numero", "y": 4.6, "s": 0, "c": 0, "t": 1},  # tipo incorrecto
    ],
)
def test_invalid_position_becomes_none_but_unit_is_kept(bad_pos: dict[str, Any]) -> None:
    # Un GPS con datos basura no debe tumbar el vehículo: se trata como "sin posición".
    unit = RawUnit.model_validate(_unit(pos=bad_pos))

    assert unit.pos is None
    assert unit.nm == "Bus 1"


def test_valid_position_is_parsed_with_its_units() -> None:
    pos = RawUnit.model_validate(_unit()).pos

    assert pos == RawPosition(x=-74.08, y=4.6, s=30, c=90, t=1_700_000_000, z=2600.0, sc=0)


def test_unit_without_id_is_skipped_and_the_rest_survive() -> None:
    # Un elemento corrupto no debe vaciar toda la flota.
    units = parse_units([_unit(id=1), {"nm": "sin id"}, _unit(id=3)])

    assert [u.id for u in units] == [1, 3]


def test_models_are_immutable() -> None:
    unit = RawUnit.model_validate(_unit())

    with pytest.raises(ValidationError):
        unit.nm = "otro nombre"  # type: ignore[misc]


def test_resource_without_people_blocks_defaults_to_empty() -> None:
    # Sin los flags de conductores/pasajeros Wialon omite drvrs/tags: no debe fallar.
    resource = parse_resources([{"id": 9, "nm": "Recurso", "mu": 3, "uacl": 1}])[0]

    assert resource.drvrs == {}
    assert resource.tags == {}
