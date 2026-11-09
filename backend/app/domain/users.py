"""Entidad de dominio ``User`` y regla de contraseñas (solo librería estándar).

Inmutable (``frozen=True``): cambiar algo (p. ej. un intento fallido) crea un
objeto NUEVO con ``dataclasses.replace``; el repositorio persiste ese objeto.
"""

import re
import secrets
import string
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from app.domain.permissions import Permission

PASSWORD_MIN_LENGTH = 12  # NIST SP 800-63B: priorizar longitud sobre reglas raras
PASSWORD_MAX_LENGTH = 128  # tope: evita DoS con contraseñas enormes en Argon2


@dataclass(frozen=True)
class User:
    """Usuario de la plataforma (NO es un usuario de Wialon)."""

    id: int
    email: str
    full_name: str
    password_hash: str  # hash Argon2; la contraseña en claro nunca se guarda
    role: str  # nombre del rol (RoleName); los permisos vienen de la BD
    permissions: frozenset[str]
    is_active: bool = True
    must_change_password: bool = False  # RF-06: obligatorio en el primer inicio de sesión
    failed_login_attempts: int = 0
    locked_until: datetime | None = None  # UTC; None = no bloqueado

    def can(self, permission: Permission | str) -> bool:
        """¿Tiene el usuario este permiso? Única pregunta que hacen los endpoints."""
        return self.is_active and str(permission) in self.permissions

    def is_locked(self, now: datetime) -> bool:
        """Bloqueo temporal por intentos fallidos (SEG-07)."""
        return self.locked_until is not None and now < self.locked_until

    def with_failed_attempt(self, now: datetime, max_attempts: int, lockout: timedelta) -> "User":
        """Registra un intento fallido; al llegar al máximo, bloquea la cuenta un tiempo."""
        attempts = self.failed_login_attempts + 1
        if attempts >= max_attempts:
            # Al bloquear se reinicia el contador: tras el bloqueo hay otra tanda de intentos.
            return replace(self, failed_login_attempts=0, locked_until=now + lockout)
        return replace(self, failed_login_attempts=attempts)

    def with_successful_login(self) -> "User":
        """Login correcto: limpia contador y bloqueo."""
        return replace(self, failed_login_attempts=0, locked_until=None)


# Al menos una letra y un dígito: impide "aaaaaaaaaaaa" o "123456789012".
_HAS_LETTER = re.compile(r"[^\W\d_]")
_HAS_DIGIT = re.compile(r"\d")


TEMPORARY_PASSWORD_LENGTH = 16
# Sin caracteres ambiguos (0/O, 1/l/I): el Admin la dicta o copia al usuario sin errores.
_TEMP_ALPHABET = "".join(c for c in string.ascii_letters + string.digits if c not in "0O1lI")


def generate_temporary_password() -> str:
    """Contraseña temporal aleatoria (CSPRNG) que cumple la política (RF-06).

    Solo sirve para el primer ingreso: ``must_change_password`` obliga a cambiarla.
    """
    while True:  # reintenta (casi nunca) hasta tener letras Y dígitos
        candidate = "".join(secrets.choice(_TEMP_ALPHABET) for _ in range(TEMPORARY_PASSWORD_LENGTH))
        if _HAS_LETTER.search(candidate) and _HAS_DIGIT.search(candidate):
            return candidate


def password_policy_errors(password: str, email: str) -> list[str]:
    """Devuelve los incumplimientos de la política de contraseñas (lista vacía = válida)."""
    errors: list[str] = []
    if len(password) < PASSWORD_MIN_LENGTH:
        errors.append(f"Debe tener al menos {PASSWORD_MIN_LENGTH} caracteres.")
    if len(password) > PASSWORD_MAX_LENGTH:
        errors.append(f"Debe tener como máximo {PASSWORD_MAX_LENGTH} caracteres.")
    if not _HAS_LETTER.search(password) or not _HAS_DIGIT.search(password):
        errors.append("Debe combinar letras y números.")
    local_part = email.split("@", 1)[0].lower()
    if len(local_part) >= 3 and local_part in password.lower():
        errors.append("No debe contener tu correo.")
    return errors
