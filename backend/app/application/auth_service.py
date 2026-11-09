"""Casos de uso de autenticación (RF-04, RF-06, SEG-07).

Sesión = dos credenciales con vidas distintas:
- **Access token** (JWT, 15 min): se valida sin ir a la BD de tokens. Corto para
  que, si se filtra, sirva poco tiempo.
- **Refresh token** (opaco, 7 días): solo se guarda su HASH SHA-256. ROTATORIO:
  cada uso lo invalida y emite uno nuevo de la misma "familia". Si llega uno ya
  usado, alguien lo robó (el legítimo ya lo había rotado) -> se revoca TODA la
  familia y se audita ("detección de reutilización", recomendación OWASP).

Login seguro:
- Mensaje de error genérico (no revela si el correo existe).
- Si el correo no existe, se verifica igual contra un hash ficticio: así el
  tiempo de respuesta no delata qué correos están registrados.
- Bloqueo temporal tras N intentos fallidos (además del rate limit por IP).
"""

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import NoReturn

from app.application.audit_service import AuditService
from app.application.errors import InvalidCredentials, InvalidSession, ValidationFailed
from app.application.ports import (
    AccessTokenService,
    PasswordHasher,
    RefreshTokenRecord,
    RefreshTokenStore,
    UnitOfWork,
    UserRepository,
)
from app.domain.users import User, password_policy_errors

REFRESH_TOKEN_BYTES = 32  # 256 bits de entropía


@dataclass(frozen=True)
class AuthPolicy:
    max_failed_attempts: int = 5
    lockout: timedelta = timedelta(minutes=15)
    refresh_ttl: timedelta = timedelta(days=7)


@dataclass(frozen=True)
class AuthSession:
    """Resultado de login/refresh: el usuario y las credenciales para las cookies."""

    user: User
    access_token: str
    refresh_token: str  # valor EN CLARO: solo viaja en la cookie, nunca se persiste


def hash_refresh_token(raw: str) -> str:
    """SHA-256 basta aquí (token aleatorio de 256 bits, no una contraseña humana)."""
    return hashlib.sha256(raw.encode()).hexdigest()


class AuthService:
    def __init__(
        self,
        *,
        users: UserRepository,
        refresh_tokens: RefreshTokenStore,
        hasher: PasswordHasher,
        access_tokens: AccessTokenService,
        audit: AuditService,
        uow: UnitOfWork,
        clock: Callable[[], datetime],
        policy: AuthPolicy | None = None,
    ) -> None:
        self._users = users
        self._refresh_tokens = refresh_tokens
        self._hasher = hasher
        self._access_tokens = access_tokens
        self._audit = audit
        self._uow = uow
        self._clock = clock
        self._policy = policy or AuthPolicy()
        # Hash ficticio para igualar el tiempo cuando el correo no existe.
        self._dummy_hash = hasher.hash(secrets.token_urlsafe(16))

    # ------------------------------------------------------------------ login
    async def login(self, email: str, password: str, ip: str | None) -> AuthSession:
        email = email.strip().lower()
        user = await self._users.get_by_email(email)
        now = self._clock()

        if user is None:
            self._hasher.verify(self._dummy_hash, password)  # mismo coste que un usuario real
            await self._reject(email, ip, reason="unknown_email")
        if user.is_locked(now):
            await self._reject(email, ip, reason="account_locked", user=user)
        if not self._hasher.verify(user.password_hash, password):
            await self._register_failure(user, ip, now)
        if not user.is_active:
            await self._reject(email, ip, reason="inactive", user=user)

        user = user.with_successful_login()
        await self._users.save_login_state(user)
        await self._upgrade_hash_if_needed(user, password)
        session = await self._start_session(user, family_id=secrets.token_hex(16))
        await self._audit.record("auth.login_succeeded", actor=user, ip_address=ip)
        await self._uow.commit()
        return session

    async def _register_failure(self, user: User, ip: str | None, now: datetime) -> NoReturn:
        updated = user.with_failed_attempt(
            now, self._policy.max_failed_attempts, self._policy.lockout
        )
        await self._users.save_login_state(updated)
        if updated.locked_until is not None:
            await self._audit.record(
                "auth.account_locked", actor=user, ip_address=ip,
                details={"locked_until": updated.locked_until.isoformat()},
            )
        await self._reject(user.email, ip, reason="wrong_password", user=user)

    async def _reject(
        self, email: str, ip: str | None, *, reason: str, user: User | None = None
    ) -> NoReturn:
        """Audita el intento fallido, CONFIRMA (para no perder contador/auditoría) y lanza 401."""
        await self._audit.record(
            "auth.login_failed", actor=user, actor_email=email, ip_address=ip,
            details={"reason": reason},  # el motivo real queda solo en auditoría, no en la respuesta
        )
        await self._uow.commit()
        raise InvalidCredentials

    async def _upgrade_hash_if_needed(self, user: User, password: str) -> None:
        """Si cambian los parámetros de Argon2, el hash se actualiza en el siguiente login."""
        if self._hasher.needs_rehash(user.password_hash):
            await self._users.update_password(
                user.id, self._hasher.hash(password), user.must_change_password
            )

    # ---------------------------------------------------------------- refresh
    async def refresh(self, raw_refresh_token: str | None, ip: str | None) -> AuthSession:
        if not raw_refresh_token:
            raise InvalidSession
        now = self._clock()
        record = await self._refresh_tokens.get(hash_refresh_token(raw_refresh_token))
        if record is None:
            raise InvalidSession
        if record.revoked_at is not None:
            # Token YA usado: robo probable -> se cierra la sesión entera (toda la familia).
            await self._refresh_tokens.revoke_family(record.family_id, now)
            await self._audit.record(
                "auth.refresh_reuse_detected", entity_type="user", entity_id=record.user_id,
                ip_address=ip,
            )
            await self._uow.commit()
            raise InvalidSession
        if record.expires_at <= now:
            raise InvalidSession

        user = await self._users.get_by_id(record.user_id)
        if user is None or not user.is_active:
            await self._refresh_tokens.revoke_family(record.family_id, now)
            await self._uow.commit()
            raise InvalidSession

        await self._refresh_tokens.revoke(record.token_hash, now)  # rotación: el viejo muere
        session = await self._start_session(user, family_id=record.family_id)
        await self._uow.commit()
        return session

    # ----------------------------------------------------------------- logout
    async def logout(self, raw_refresh_token: str | None, actor: User | None, ip: str | None) -> None:
        """Invalida la sesión en el SERVIDOR (no basta con borrar cookies, SEG-07)."""
        if raw_refresh_token:
            record = await self._refresh_tokens.get(hash_refresh_token(raw_refresh_token))
            if record is not None:
                await self._refresh_tokens.revoke_family(record.family_id, self._clock())
        await self._audit.record("auth.logout", actor=actor, ip_address=ip)
        await self._uow.commit()

    # -------------------------------------------------------- change password
    async def change_password(
        self, user: User, current_password: str, new_password: str, ip: str | None
    ) -> AuthSession:
        """Cambia la contraseña, cierra las demás sesiones y abre una nueva."""
        if not self._hasher.verify(user.password_hash, current_password):
            raise ValidationFailed(
                "No se pudo cambiar la contraseña.",
                {"current_password": ["La contraseña actual no es correcta."]},
            )
        problems = password_policy_errors(new_password, user.email)
        if current_password == new_password:
            problems.append("Debe ser distinta de la contraseña actual.")
        if problems:
            raise ValidationFailed("La nueva contraseña no cumple la política.", {"new_password": problems})

        now = self._clock()
        await self._users.update_password(user.id, self._hasher.hash(new_password), False)
        await self._refresh_tokens.revoke_all_for_user(user.id, now)  # cierra otras sesiones
        refreshed = await self._users.get_by_id(user.id)
        session = await self._start_session(refreshed or user, family_id=secrets.token_hex(16))
        await self._audit.record("auth.password_changed", actor=user, ip_address=ip)
        await self._uow.commit()
        return session

    # ---------------------------------------------------------------- helpers
    async def current_user(self, access_token: str | None) -> User:
        """Usuario de la cookie de acceso. Se lee de la BD en cada petición: un usuario
        desactivado o con rol cambiado pierde el acceso de inmediato (no al expirar el JWT)."""
        user_id = self._access_tokens.user_id_from(access_token) if access_token else None
        user = await self._users.get_by_id(user_id) if user_id is not None else None
        if user is None or not user.is_active:
            raise InvalidSession
        return user

    async def _start_session(self, user: User, family_id: str) -> AuthSession:
        raw = secrets.token_urlsafe(REFRESH_TOKEN_BYTES)
        await self._refresh_tokens.add(
            RefreshTokenRecord(
                token_hash=hash_refresh_token(raw),
                user_id=user.id,
                family_id=family_id,
                expires_at=self._clock() + self._policy.refresh_ttl,
            )
        )
        return AuthSession(user=user, access_token=self._access_tokens.issue(user.id), refresh_token=raw)
