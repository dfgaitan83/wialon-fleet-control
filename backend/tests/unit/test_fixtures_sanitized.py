"""Guardia de seguridad: las fixtures versionadas NO pueden contener datos sensibles.

¿Por qué existe? Incidente real (2026-11-09): la primera versión de las fixtures
publicó en el repositorio (público) contraseñas de dispositivos (psw), claves de
conductores (pwd), teléfonos y documentos de identidad. Este test falla si alguien
regenera las fixtures sin enmascarar, ANTES de que lleguen a GitHub.
"""

import json
import re
from pathlib import Path

import pytest

from scripts.wialon_explorer import (
    REDACTED,
    classify_field_name,
    mask_value,
    redact_resources,
    redact_units,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "wialon"
# Un valor enmascarado solo deja ver (como mucho) los 2 últimos caracteres.
MASKED = re.compile(r"^\+?\*+.{0,2}$")


def _load(name: str):
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _people(resources: list[dict]) -> list[dict]:
    return [p for res in resources for g in ("drvrs", "tags") for p in (res.get(g) or {}).values()]


def _is_masked(value: object) -> bool:
    return value in (None, "", REDACTED) or bool(MASKED.match(str(value)))


# ---------------- Las fixtures REALES están limpias ----------------


def test_login_fixture_has_no_session_or_token() -> None:
    assert {"eid", "th", "gis_sid", "host", "token"}.isdisjoint(_load("login"))


@pytest.mark.parametrize("field", ["psw", "ph", "ph2"])
def test_units_fixed_sensitive_fields_are_masked(field: str) -> None:
    offenders = [u["id"] for u in _load("units") if not _is_masked(u.get(field))]
    assert offenders == [], f"{field} sin enmascarar en unidades {offenders}"


def test_units_personal_custom_fields_are_masked() -> None:
    for unit in _load("units"):
        for field in (unit.get("flds") or {}).values():
            if classify_field_name(str(field.get("n", ""))):
                assert _is_masked(field.get("v")), (unit["id"], field.get("n"))


def test_people_fixed_sensitive_fields_are_masked() -> None:
    for person in _people(_load("resources")):
        assert _is_masked(person.get("pwd")), person.get("id")
        assert _is_masked(person.get("p")), person.get("id")


def test_people_names_are_pseudonymized() -> None:
    for res in _load("resources"):
        for group, label in (("drvrs", "Conductor"), ("tags", "Pasajero")):
            for person in (res.get(group) or {}).values():
                assert person["n"] == f"{label} {person['id']}"


def test_people_custom_fields_are_masked() -> None:
    for person in _people(_load("resources")):
        for name, value in (person.get("jp") or {}).items():
            if classify_field_name(name):
                assert _is_masked(value), (person.get("id"), name)


# ---------------- Reglas de enmascarado (datos ficticios) ----------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Password", "secret"),
        ("clave app", "secret"),
        ("cedula", "personal"),
        ("C.C", "personal"),
        ("ID", "personal"),
        ("colaborador - número de documento", "personal"),
        ("PROPIETARIO", "personal"),
        ("ICCID", "personal"),
        ("Route", None),
        ("cargo", None),
        ("MARCA", None),
    ],
)
def test_classify_field_name(name: str, expected: str | None) -> None:
    assert classify_field_name(name) == expected


def test_mask_value_keeps_format_and_last_two_chars() -> None:
    assert mask_value("+570000000033") == "+**********33"
    assert mask_value("0000000044") == "********44"
    assert mask_value("1") == REDACTED


def test_redact_units_masks_fixed_and_custom_fields_without_mutating() -> None:
    flds = {"1": {"id": 1, "n": "PROPIETARIO", "v": "NOMBRE FALSO"}, "2": {"id": 2, "n": "MARCA", "v": "BUS"}}
    original = [{"id": 1, "psw": "falso-1", "ph": "+570000000099", "nm": "Bus", "flds": flds}]

    unit = redact_units(original)[0]

    assert unit["psw"] == REDACTED
    assert unit["ph"] == "+**********99"
    assert unit["flds"]["1"]["v"] == "**********SO"  # propietario enmascarado
    assert unit["flds"]["2"]["v"] == "BUS"  # dato no personal intacto
    assert original[0]["flds"]["1"]["v"] == "NOMBRE FALSO"  # inmutabilidad


def test_redact_resources_masks_driver_pwd_phone_and_documents() -> None:
    driver = {"id": 4, "n": "Ana", "pwd": "falso-2", "p": "+570000000011", "jp": {"cedula": "0000000077"}}
    redacted = redact_resources([{"id": 1, "drvrs": {"4": driver}}])[0]["drvrs"]["4"]

    assert redacted["pwd"] == REDACTED
    assert redacted["p"] == "+**********11"
    assert redacted["jp"]["cedula"] == "********77"
    assert redacted["n"] == "Conductor 4"  # seudónimo estable basado en el id
    assert redacted["id"] == 4  # el id (usado en relaciones) se conserva
