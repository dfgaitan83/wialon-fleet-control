"""Servicio de auditoría (RF-26, SEG-09): punto ÚNICO para registrar eventos.

Todos los casos de uso llaman a ``record(...)`` en vez de escribir en la tabla:
así el formato es uniforme y es imposible "olvidar" la hora o el actor.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.application.ports import AuditEntry, AuditLog
from app.domain.users import User

# Claves que NUNCA se guardan en ``details`` aunque alguien las pase por error.
_FORBIDDEN_DETAIL_KEYS = frozenset({"password", "new_password", "current_password", "token"})


class AuditService:
    def __init__(self, log: AuditLog, clock: Callable[[], datetime]) -> None:
        self._log = log
        self._clock = clock

    async def record(
        self,
        action: str,
        *,
        actor: User | None = None,
        actor_email: str | None = None,
        entity_type: str | None = None,
        entity_id: str | int | None = None,
        ip_address: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Registra un evento. ``actor_email`` sirve cuando no hay usuario (login fallido)."""
        safe_details = (
            {k: v for k, v in details.items() if k not in _FORBIDDEN_DETAIL_KEYS} if details else None
        )
        await self._log.add(
            AuditEntry(
                action=action,
                occurred_at=self._clock(),
                actor_user_id=actor.id if actor else None,
                actor_email=actor.email if actor else actor_email,
                entity_type=entity_type,
                entity_id=str(entity_id) if entity_id is not None else None,
                ip_address=ip_address,
                details=safe_details,
            )
        )
