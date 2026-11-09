"""Logging estructurado con structlog y redacción de secretos (ARQ-07, SEG-09).

- Producción: una línea JSON por evento (fácil de filtrar en Render).
- Desarrollo: salida legible en consola.
- Los ``logging.getLogger(...)`` de la librería estándar (p. ej. el cliente de
  Wialon) pasan por el MISMO formateador, así todo sale con el mismo formato.
- ``redact_secrets``: cualquier clave con nombre sensible (password, token,
  cookie, authorization...) se reemplaza por ``[REDACTED]``, y cualquier cadena
  hexadecimal larga (formato de token de Wialon) se enmascara aunque llegue
  dentro de un mensaje. Defensa en profundidad: aunque alguien loguee por error.
"""

import logging
import re
from typing import Any

import structlog

REDACTED = "[REDACTED]"
# Palabras completas separadas por "_": "access_token" o "password" sí; "passengers" NO.
_SENSITIVE_KEY = re.compile(
    r"(?:^|_)(?:pass(?:word)?|pwd|psw|token|secret|authorization|cookie|csrf|sid)(?:$|_)",
    re.IGNORECASE,
)
_LONG_HEX = re.compile(r"\b[0-9a-fA-F]{40,}\b")  # tokens de Wialon (72 hex), hashes SHA-256...


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return _LONG_HEX.sub(REDACTED, value)
    if isinstance(value, dict):
        return {k: REDACTED if _SENSITIVE_KEY.search(str(k)) else _redact_value(v) for k, v in value.items()}
    return value


def redact_secrets(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Procesador de structlog: devuelve un evento NUEVO sin datos sensibles."""
    return {
        key: REDACTED if key != "event" and _SENSITIVE_KEY.search(key) else _redact_value(value)
        for key, value in event_dict.items()
    }


def configure_logging(*, json_output: bool, level: int = logging.INFO) -> None:
    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,  # request_id y similares
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        redact_secrets,
    ]
    renderer: Any = (
        structlog.processors.JSONRenderer() if json_output else structlog.dev.ConsoleRenderer(colors=False)
    )
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=[*shared, structlog.stdlib.ExtraAdder()],
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            renderer,
        ],
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]  # reemplaza handlers previos (evita líneas duplicadas)
    root.setLevel(level)
    # httpx registra CADA petición a Wialon en INFO: ruido sin valor (nuestro cliente ya
    # registra los fallos). Solo advertencias y errores.
    logging.getLogger("httpx").setLevel(logging.WARNING)
