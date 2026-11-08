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

REDACTED = "***"  # valor que reemplaza a los datos sensibles en las fixtures
# Si el nombre de un campo jp contiene alguna de estas palabras, su valor se oculta.
SENSITIVE_JP_KEYWORDS = ("password", "contraseña", "clave", "pin")

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


def _redact_jp(jp: dict[str, Any]) -> dict[str, Any]:
    """Devuelve un jp NUEVO con los campos sensibles enmascarados (no modifica el original)."""
    return {
        # Si la clave (en minúsculas) contiene "password", "clave"... se reemplaza el valor.
        k: (REDACTED if any(w in k.lower() for w in SENSITIVE_JP_KEYWORDS) else v)
        for k, v in jp.items()
    }


def _redact_people(people: dict[str, Any]) -> dict[str, Any]:
    """Aplica _redact_jp a cada persona (conductor o pasajero) del diccionario {id: persona}."""
    # {**p, "jp": ...} copia la persona y sustituye solo su jp -> inmutabilidad.
    return {pid: {**p, "jp": _redact_jp(p.get("jp") or {})} for pid, p in people.items()}


def redact_resources(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Copia de los recursos con contraseñas de ``jp`` enmascaradas (conductores y pasajeros).

    Pública porque la usa el test ``test_redact_resources_masks_passwords_without_mutating``.
    """
    return [
        # Copia el recurso y reemplaza solo "drvrs"/"tags" cuando existen y no están vacíos.
        {**res, **{k: _redact_people(res[k]) for k in ("drvrs", "tags") if res.get(k)}}
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

    resources = redact_resources(resources)  # enmascarar ANTES de imprimir o guardar
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
