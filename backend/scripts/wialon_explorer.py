"""Meta M1: explorador de la cuenta Wialon (SOLO LECTURA).

Qué hace:
1. Login con el token del ``.env`` usando el cliente único (``app/infrastructure/wialon/client.py``).
2. Lista vehículos (``avl_unit``) y recursos (``avl_resource``) con flags en decimal.
3. Imprime un resumen: vehículos con posición, conductores, pasajeros y permisos (``uacl``).
4. Guarda el JSON crudo en ``tests/fixtures/wialon/``: son las fixtures oficiales para
   tests y mappers (permiten probar sin llamar a Wialon real).

Reglas que respeta:
- NO crea, edita ni borra nada: la cuenta demoApps es compartida con otros candidatos.
- Las fixtures no contienen secretos: el cliente quita token/sid del login y aquí
  se enmascaran las contraseñas que algunos pasajeros tienen en su ``jp``.

Uso (desde backend/):
    python -m uv run python -m scripts.wialon_explorer
"""

import asyncio  # el cliente es asíncrono -> se ejecuta con asyncio.run
import json  # para escribir las fixtures
import sys  # sys.exit con código de salida (0 = ok, 1 = fallo)
from datetime import UTC, datetime  # conversión de Unix -> texto, siempre en UTC
from pathlib import Path
from typing import Any

# Se REUTILIZA el cliente (nada de llamadas HTTP propias). Un script es capa externa:
# puede usar infraestructura directamente.
from app.core.config import get_settings
from app.infrastructure.wialon.client import (
    RESOURCE_FLAGS_EXPLORE,
    UNIT_FLAGS_EXPLORE,
    WialonClient,
)
from app.infrastructure.wialon.errors import WialonError

# backend/tests/fixtures/wialon, calculado desde este archivo (backend/scripts/...).
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "wialon"
MAX_ROWS = 25  # filas máximas por tabla en consola; el detalle completo queda en la fixture

# Valores del campo "mu" (measure units) de Wialon.
# HALLAZGO: en demoApps todo viene con mu=3 (métrico + galones US). La velocidad
# con mu=3 YA está en km/h; convertir "si mu != 0" sería un error.
MEASURE_UNITS = {
    0: "métrico (km/h)",
    1: "US (mph)",
    2: "imperial (mph)",
    3: "métrico + galones US (km/h)",
}
MPH_MEASURE_UNITS = frozenset({1, 2})  # SOLO estos requieren convertir mph -> km/h en los mappers

REDACTED = "***"  # valor que reemplaza por COMPLETO a los secretos
VISIBLE_TAIL = 2  # en identificadores se conservan los 2 últimos caracteres (formato útil a tests)

# INCIDENTE CORREGIDO (2026-11-09): la primera versión solo enmascaraba contraseñas
# del jp y publicó en el repo (público) datos sensibles de la cuenta compartida.
# Regla única, aplicada por NOMBRE de campo:
#   - SECRETO  -> "***" (contraseñas, claves).
#   - PERSONAL -> enmascarado parcial (documentos, teléfonos, propietario, SIM...).

# Campos FIJOS de Wialon (nombre exacto de la clave en el JSON):
UNIT_SECRET_KEYS = frozenset({"psw"})  # contraseña del dispositivo GPS
UNIT_PERSONAL_KEYS = frozenset({"ph", "ph2"})  # teléfonos de la SIM del equipo
PERSON_SECRET_KEYS = frozenset({"pwd"})  # clave móvil del conductor (app de Wialon)
PERSON_PERSONAL_KEYS = frozenset({"p"})  # teléfono del conductor/pasajero

# Campos PERSONALIZADOS (jp de personas, flds de unidades): los nombra cada empresa,
# así que se reconocen por palabras clave dentro del nombre (en minúsculas).
SECRET_NAME_KEYWORDS = ("password", "contraseña", "clave", "pin", "pwd")
PERSONAL_NAME_KEYWORDS = (
    "cedula", "cédula", "c.c", "documento", "nacimiento", "licencia", "nit",
    "iccid", "propietario", "propoietario", "chasis", "motor", "telefono", "teléfono", "celular",
)  # fmt: skip
PERSONAL_EXACT_NAMES = frozenset({"cc", "id"})  # demasiado cortos para buscarlos como subcadena

# Bits estándar de "uacl" (permisos del usuario actual sobre el objeto).
# uacl es un entero donde cada bit es un permiso: se comprueban con "&" (AND binario).
ACL_BITS = {
    0x1: "ver",
    0x2: "ver props detalladas",
    0x4: "gestionar accesos",
    0x8: "borrar",
    0x10: "renombrar",
    0x20: "ver campos custom",
    0x40: "editar campos custom",
    0x80: "editar otras props",
    0x200: "consultar mensajes/reportes",
}


def _utc(ts: int | None) -> str:
    """Unix timestamp -> texto en UTC. La hora de Bogotá se calcula en el frontend."""
    if not ts:  # None o 0: unidad sin mensajes
        return "-"
    return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def _acl(uacl: int | None) -> str:
    """Traduce el entero uacl a la lista de permisos legibles."""
    if uacl is None:
        return "desconocido"
    # uacl & bit != 0 -> ese permiso está activo.
    names = [name for bit, name in ACL_BITS.items() if uacl & bit]
    return f"{uacl} ({', '.join(names) or 'sin bits estándar'})"


def mask_value(value: str) -> str:
    """Enmascara conservando longitud y los 2 últimos caracteres.

    "+573117382120" -> "+**********20"   |   "1020304050" -> "********50"
    """
    if len(value) <= VISIBLE_TAIL:
        return REDACTED
    prefix = "+" if value.startswith("+") else ""  # el "+" internacional no es dato sensible
    hidden = value[len(prefix) : -VISIBLE_TAIL]
    return f"{prefix}{'*' * len(hidden)}{value[-VISIBLE_TAIL:]}"


def classify_field_name(name: str) -> str | None:
    """Clasifica un campo PERSONALIZADO por su nombre: "secret", "personal" o None."""
    lowered = name.strip().lower()
    if any(word in lowered for word in SECRET_NAME_KEYWORDS):
        return "secret"
    if lowered in PERSONAL_EXACT_NAMES or any(word in lowered for word in PERSONAL_NAME_KEYWORDS):
        return "personal"
    return None


def _apply(kind: str | None, value: Any) -> Any:
    """Aplica la regla al valor (solo si tiene contenido)."""
    if not value or kind is None:
        return value
    if kind == "secret":
        return REDACTED
    return mask_value(str(value))


def _redact_jp(jp: dict[str, Any]) -> dict[str, Any]:
    """jp NUEVO ({nombre: valor}) con secretos y datos personales enmascarados."""
    return {name: _apply(classify_field_name(name), value) for name, value in jp.items()}


def _redact_flds(flds: dict[str, Any]) -> dict[str, Any]:
    """flds NUEVO ({id: {"n": nombre, "v": valor}}): se clasifica por "n" y se enmascara "v"."""
    return {
        fid: {**field, "v": _apply(classify_field_name(str(field.get("n", ""))), field.get("v"))}
        for fid, field in flds.items()
    }


def _redact_fixed(
    item: dict[str, Any], secret_keys: frozenset[str], personal_keys: frozenset[str]
) -> dict[str, Any]:
    """Copia NUEVA del objeto aplicando la regla a los campos FIJOS de Wialon."""
    return {
        key: _apply(
            "secret" if key in secret_keys else "personal" if key in personal_keys else None, value
        )
        for key, value in item.items()
    }


def _redact_people(people: dict[str, Any], label: str) -> dict[str, Any]:
    """Enmascara cada persona del diccionario {id: persona} y SEUDONIMIZA su nombre.

    El nombre real ("n") se reemplaza por "<label> <id>" (ej. "Conductor 12"): es estable
    (mismo id -> mismo seudónimo), así que los tests y las relaciones por id siguen valiendo.
    """
    return {
        pid: {
            **_redact_fixed(p, PERSON_SECRET_KEYS, PERSON_PERSONAL_KEYS),  # pwd y teléfono
            "n": f"{label} {p.get('id', pid)}",  # seudónimo en lugar del nombre real
            "jp": _redact_jp(p.get("jp") or {}),  # campos personalizados (cédula, documento...)
        }
        for pid, p in people.items()
    }


# Seudónimo por tipo de persona: clave del recurso en Wialon -> etiqueta.
PEOPLE_LABELS = {"drvrs": "Conductor", "tags": "Pasajero"}


def redact_units(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Copia de las unidades: sin contraseña del equipo, teléfonos y campos personales enmascarados."""
    return [
        {
            **_redact_fixed(unit, UNIT_SECRET_KEYS, UNIT_PERSONAL_KEYS),
            **({"flds": _redact_flds(unit["flds"])} if unit.get("flds") else {}),
        }
        for unit in units
    ]


def redact_resources(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Copia de los recursos con conductores y pasajeros enmascarados y seudonimizados.

    Pública porque la usan los tests de enmascarado.
    """
    return [
        # Copia el recurso y reemplaza solo "drvrs"/"tags" cuando existen y no están vacíos.
        {**res, **{k: _redact_people(res[k], label) for k, label in PEOPLE_LABELS.items() if res.get(k)}}
        for res in resources
    ]


def _save_fixture(name: str, data: Any) -> Path:
    """Escribe ``<name>.json`` en la carpeta de fixtures y devuelve su ruta."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)  # crea la carpeta si no existe
    path = FIXTURES_DIR / f"{name}.json"
    # ensure_ascii=False conserva tildes/ñ legibles; indent=2 facilita revisar los diffs en git.
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _print_units(units: list[dict[str, Any]]) -> None:
    """Resumen de vehículos: posición, velocidad, unidades de medida y permisos."""
    with_pos = [u for u in units if u.get("pos")]  # "pos" solo existe si la unidad ha reportado
    print(f"\n=== VEHÍCULOS: {len(units)} (con posición: {len(with_pos)}) ===")
    for unit in units[:MAX_ROWS]:
        pos = unit.get("pos") or {}  # {} evita errores con unidades sin posición
        mu = unit.get("mu")
        # En "pos" de Wialon: y = latitud, x = longitud, s = velocidad, c = rumbo, t = hora Unix.
        print(
            f"- [{unit.get('id')}] {unit.get('nm')} | mu={mu} {MEASURE_UNITS.get(mu, '?')}"
            f" | lat={pos.get('y', '-')} lon={pos.get('x', '-')} vel={pos.get('s', '-')}"
            f" rumbo={pos.get('c', '-')} | {_utc(pos.get('t'))}"
        )
        print(f"    permisos: {_acl(unit.get('uacl'))}")
    if len(units) > MAX_ROWS:
        print(f"  ... y {len(units) - MAX_ROWS} más (ver fixture)")
    # Aviso para los mappers: ¿hay alguna unidad que reporte en mph?
    mph_units = [u.get("nm") for u in units if u.get("mu") in MPH_MEASURE_UNITS]
    if mph_units:
        print(f"  ⚠ Unidades en mph (convertir a km/h en mappers): {mph_units}")
    else:
        print("  ✔ Todas las unidades reportan velocidad en km/h (mu 0 o 3)")


def _print_named_items(title: str, items: dict[str, Any] | None, fields: tuple[str, ...]) -> None:
    """Imprime un diccionario de Wialon {id: elemento} (conductores, pasajeros, grupos)."""
    values = list((items or {}).values())  # Wialon devuelve dict por id, no lista
    print(f"  {title}: {len(values)}")
    for item in values[:MAX_ROWS]:
        # Solo se muestran los campos que tienen valor, para no llenar la consola de vacíos.
        extra = " | ".join(f"{f}={item.get(f)}" for f in fields if item.get(f) not in (None, ""))
        # En recursos, el nombre del elemento es "n" (no "nm" como en unidades).
        print(f"    - [{item.get('id')}] {item.get('n')} {('| ' + extra) if extra else ''}")


def _print_resources(resources: list[dict[str, Any]]) -> None:
    """Resumen por recurso de conductores, pasajeros y sus grupos.

    Campos: c = código, ph = teléfono, bu = id del vehículo asignado (0 = ninguno),
    jp = propiedades personalizadas (cédula, licencia...). El "jp" varía por persona:
    por eso al editar (RF-27) hay que leer-fusionar-escribir el objeto completo.
    """
    print(f"\n=== RECURSOS: {len(resources)} ===")
    for res in resources:
        mu = res.get("mu")
        print(f"\n# [{res.get('id')}] {res.get('nm')} | mu={mu} {MEASURE_UNITS.get(mu, '?')}")
        print(f"  permisos: {_acl(res.get('uacl'))}")
        _print_named_items("Conductores (drvrs)", res.get("drvrs"), ("c", "ph", "bu", "jp"))
        _print_named_items("Grupos de conductores", res.get("drvrsgr"), ("drs",))  # drs = ids
        _print_named_items("Pasajeros (tags)", res.get("tags"), ("c", "ph", "bu", "jp"))
        _print_named_items("Grupos de pasajeros", res.get("tagsgr"), ("tgs",))  # tgs = ids


async def explore() -> int:
    """Flujo principal: login -> consultas -> enmascarar -> imprimir -> guardar fixtures."""
    settings = get_settings()  # lee y valida backend/.env
    print(f"Conectando a {settings.wialon_base_url} ...")
    # "async with" garantiza el logout al salir del bloque, aunque ocurra un error.
    async with WialonClient(
        settings.wialon_base_url,
        settings.wialon_token.get_secret_value(),
        settings.wialon_timeout_seconds,
    ) as client:
        session = client.session  # ya sin token/sid gracias a SENSITIVE_LOGIN_KEYS
        user = session.raw.get("user", {})
        print(f"[OK] Login: {session.user_name} (id {session.user_id})", end="")
        print(f" | mu usuario={user.get('mu')}")  # mu del usuario: unidades por defecto
        # tm = hora del servidor de Wialon (Unix UTC)
        print(f"     Hora servidor: {_utc(session.raw.get('tm'))}")

        # Secuencial a propósito (no asyncio.gather): evita el error 1003
        # "solo se permite una solicitud a la vez" por sesión.
        units = await client.search_items("avl_unit", UNIT_FLAGS_EXPLORE)
        resources = await client.search_items("avl_resource", RESOURCE_FLAGS_EXPLORE)
    # Aquí ya se cerró la sesión en Wialon; el resto trabaja con los datos en memoria.

    # Enmascarar ANTES de imprimir o guardar: nada sensible llega a consola ni a git.
    units = redact_units(units)
    resources = redact_resources(resources)
    _print_units(units)
    _print_resources(resources)

    saved = [
        _save_fixture("login", session.raw),  # respuesta de login sin secretos
        _save_fixture("units", units),  # vehículos con posición
        _save_fixture("resources", resources),  # conductores y pasajeros enmascarados
    ]
    print("\n[OK] Fixtures guardadas:")
    for path in saved:
        print(f"   {path}")
    print("[OK] Sesión cerrada.")
    return 0  # código de salida 0 = éxito


def main() -> int:
    """Ejecuta el explorador y convierte un WialonError en mensaje claro + código 1."""
    try:
        return asyncio.run(explore())  # arranca el event loop para el código asíncrono
    except WialonError as exc:
        print(f"[FALLO] {exc}")  # ej. "Wialon error 4: WRONG_TOKEN_LENGTH"
        return 1


if __name__ == "__main__":  # solo se ejecuta al correrlo como script, no al importarlo en tests
    sys.exit(main())
