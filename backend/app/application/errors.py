"""Errores de la aplicación (independientes de HTTP).

Los servicios lanzan estos errores; la capa API (``app/api/errors.py``) los
traduce a Problem Details con su código HTTP. Así los casos de uso no saben
nada de HTTP y la traducción vive en UN solo lugar.
"""


class AppError(Exception):
    """Base de los errores de negocio esperados (no son bugs: no se registran como error)."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail  # mensaje seguro para mostrar al usuario final


class InvalidCredentials(AppError):
    """Login fallido. Mensaje GENÉRICO a propósito: no revela si el correo existe (SEG-07)."""

    def __init__(self) -> None:
        super().__init__(
            "Correo o contraseña incorrectos. Tras varios intentos fallidos la cuenta "
            "se bloquea temporalmente."
        )


class InvalidSession(AppError):
    """No hay sesión válida (cookie ausente, expirada, revocada o reutilizada)."""

    def __init__(self, detail: str = "Tu sesión expiró. Inicia sesión de nuevo.") -> None:
        super().__init__(detail)


class PermissionDenied(AppError):
    """Sesión válida pero sin el permiso necesario (SEG-01: denegar por defecto)."""

    def __init__(self, detail: str = "No tienes permiso para realizar esta acción.") -> None:
        super().__init__(detail)


class PasswordChangeRequired(AppError):
    """RF-06: el usuario debe cambiar su contraseña antes de usar la plataforma."""

    def __init__(self) -> None:
        super().__init__("Debes cambiar tu contraseña antes de continuar.")


class ValidationFailed(AppError):
    """Datos inválidos con errores por campo (mismo formato que los 422 de FastAPI)."""

    def __init__(self, detail: str, errors: dict[str, list[str]]) -> None:
        super().__init__(detail)
        self.errors = errors


class ProviderUnavailable(AppError):
    """El proveedor GPS (Wialon) no responde o falló: error temporal -> 503 (INT-05)."""

    def __init__(
        self, detail: str = "El proveedor GPS no está disponible en este momento. Intenta de nuevo en unos segundos."
    ) -> None:
        super().__init__(detail)


class NotFound(AppError):
    """El recurso no existe (o no es visible para el usuario)."""


class Conflict(AppError):
    """El recurso ya existe o cambió mientras se editaba."""
