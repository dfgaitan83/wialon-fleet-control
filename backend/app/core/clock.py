"""Reloj de la aplicación. Se inyecta (``clock=utc_now``) para poder fijar la hora en tests."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Hora actual en UTC con zona (aware). Nunca usar ``datetime.now()`` sin zona."""
    return datetime.now(UTC)
