"""Adaptadores criptográficos: Argon2id para contraseñas y JWT para el access token (SEG-02).

Implementan los puertos ``PasswordHasher`` y ``AccessTokenService``.
"""

from collections.abc import Callable
from datetime import datetime, timedelta

import jwt
from argon2 import PasswordHasher as Argon2Hasher
from argon2.exceptions import InvalidHashError, VerificationError

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "wialon-fleet-api"
ACCESS_TOKEN_TYPE = "access"


class Argon2PasswordHasher:
    """Argon2id (ganador de la Password Hashing Competition, recomendado por OWASP).

    Los parámetros por defecto de argon2-cffi siguen la recomendación RFC 9106.
    Cada hash lleva su propia sal aleatoria y sus parámetros embebidos.
    """

    def __init__(self) -> None:
        self._hasher = Argon2Hasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False  # contraseña incorrecta o hash corrupto: nunca una excepción hacia arriba

    def needs_rehash(self, password_hash: str) -> bool:
        return self._hasher.check_needs_rehash(password_hash)


class JwtAccessTokenService:
    """JWT HS256 de vida corta con SOLO el id del usuario.

    Sin permisos ni datos personales dentro: un JWT se puede decodificar (no está
    cifrado) y los permisos se leen de la BD en cada petición.
    """

    def __init__(self, secret: str, ttl: timedelta, clock: Callable[[], datetime]) -> None:
        self._secret = secret
        self._ttl = ttl
        self._clock = clock

    def issue(self, user_id: int) -> str:
        now = self._clock()
        claims = {
            "sub": str(user_id),
            "typ": ACCESS_TOKEN_TYPE,
            "iss": JWT_ISSUER,
            "iat": now,
            "exp": now + self._ttl,
        }
        return jwt.encode(claims, self._secret, algorithm=JWT_ALGORITHM)

    def user_id_from(self, token: str) -> int | None:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[JWT_ALGORITHM],  # lista fija: evita el ataque "alg: none"
                issuer=JWT_ISSUER,
                options={"require": ["exp", "sub", "iss"]},
            )
        except jwt.PyJWTError:
            return None
        if claims.get("typ") != ACCESS_TOKEN_TYPE:
            return None
        try:
            return int(claims["sub"])
        except (TypeError, ValueError):
            return None
