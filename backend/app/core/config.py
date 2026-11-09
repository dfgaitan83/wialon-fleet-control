"""Configuración del backend leída desde variables de entorno / ``backend/.env``.

¿Por qué pydantic-settings?
- Valida tipos al arrancar: si falta ``WIALON_TOKEN`` o ``JWT_SECRET`` el servidor
  NO arranca y muestra un error claro (fail fast), en vez de fallar más tarde.
- Los secretos viven solo en ``.env`` (ignorado por git) o en las variables de la
  plataforma de despliegue; en el repo solo está ``.env.example``.

Separación por ambiente (ARQ-05): ``ENVIRONMENT=development|production``. En
producción se exigen reglas extra (cookies Secure, PostgreSQL, sin docs por
defecto) y el servidor se niega a arrancar si no se cumplen (SEG-05).
"""

import json
from functools import lru_cache  # para crear Settings una sola vez
from pathlib import Path  # rutas independientes del sistema operativo
from typing import Annotated, Literal, Self
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Ruta absoluta a backend/.env calculada desde ESTE archivo (backend/app/core/config.py):
# parents[0] = backend/app/core, parents[1] = backend/app, parents[2] = backend.
# Así el .env se encuentra aunque el proceso se ejecute desde otra carpeta.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

JWT_SECRET_MIN_LENGTH = 32  # HS256 necesita al menos 256 bits de clave
DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./local.db"


def normalize_database_url(raw: str) -> str:
    """Acepta la URL tal cual la copia Neon ("postgresql://...?sslmode=require").

    asyncpg necesita el esquema ``postgresql+asyncpg`` y el parámetro ``ssl``
    (no entiende ``sslmode`` ni ``channel_binding``, que son de libpq).
    """
    if not raw.startswith(("postgres://", "postgresql://")):
        return raw
    parts = urlsplit(raw)
    query = dict(parse_qsl(parts.query))
    query.pop("channel_binding", None)
    if "sslmode" in query:
        query["ssl"] = query.pop("sslmode")
    return urlunsplit(parts._replace(scheme="postgresql+asyncpg", query=urlencode(query)))


def _normalize_secret_url(value: object) -> object:
    raw = value.get_secret_value() if isinstance(value, SecretStr) else value
    return normalize_database_url(raw) if isinstance(raw, str) else value


class DatabaseSettings(BaseSettings):
    """Solo la BD: lo que necesitan Alembic y el seed (no exigen token de Wialon ni JWT)."""

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    database_url: SecretStr = SecretStr(DEFAULT_DATABASE_URL)

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize(cls, value: object) -> object:
        return _normalize_secret_url(value)


class Settings(BaseSettings):
    """Variables de configuración. El nombre del atributo = variable en MAYÚSCULAS.

    Ej.: ``wialon_token`` se lee de ``WIALON_TOKEN``. Las variables de entorno
    del sistema tienen prioridad sobre el archivo .env (útil en despliegue).
    """

    # Indica de qué archivo leer y con qué codificación (tildes/ñ sin problemas).
    # env_ignore_empty: "DOCS_ENABLED=" (vacío) cuenta como "no definida" -> valor por defecto.
    model_config = SettingsConfigDict(
        env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore", env_ignore_empty=True
    )

    environment: Literal["development", "production"] = "development"

    # --- Wialon ---
    # SecretStr: print(settings) muestra '**********'; el valor real solo se obtiene
    # explícitamente con .get_secret_value(). Evita filtrar el token en logs.
    wialon_token: SecretStr  # obligatorio (sin valor por defecto)
    wialon_base_url: str = "https://hst-api.wialon.com/wialon/ajax.html"  # endpoint único
    # Tiempo máximo por petición a Wialon (plan M1: 10 s). Si Wialon no responde, la
    # API devuelve error en vez de dejar al usuario esperando indefinidamente.
    wialon_timeout_seconds: float = 10.0

    # --- Base de datos ---
    # Local: SQLite (sin instalar nada). Producción: PostgreSQL (Neon) con asyncpg.
    database_url: SecretStr = SecretStr(DEFAULT_DATABASE_URL)

    # --- Autenticación (SEG-07) ---
    jwt_secret: SecretStr  # obligatorio; generar con: python -c "import secrets; print(secrets.token_urlsafe(48))"
    access_token_minutes: int = Field(default=15, ge=1, le=60)
    refresh_token_days: int = Field(default=7, ge=1, le=30)
    login_max_attempts: int = Field(default=5, ge=3, le=20)
    login_lockout_minutes: int = Field(default=15, ge=1, le=1440)
    login_rate_limit: str = "10/minute"  # por IP (slowapi); el bloqueo por cuenta es aparte
    # Secure=True: el navegador solo envía la cookie por HTTPS (localhost cuenta como seguro).
    cookie_secure: bool = True

    # --- HTTP ---
    # Orígenes que pueden llamar al backend desde el navegador (5173 = puerto de Vite).
    # NoDecode: se acepta "https://a.app,https://b.app" además de JSON '["https://a.app"]'
    # (más fácil de escribir sin errores en el panel de Render).
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    # Swagger/OpenAPI. En producción queda apagado salvo que se active a propósito (SEG-05).
    docs_enabled: bool | None = None

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: object) -> object:
        return _normalize_secret_url(value)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> object:
        """Lista JSON o separada por comas; sin espacios ni "/" final (el navegador no lo envía)."""
        if not isinstance(value, str):
            return value
        text = value.strip()
        items = json.loads(text) if text.startswith("[") else text.split(",")
        return [str(item).strip().rstrip("/") for item in items if str(item).strip()]

    @model_validator(mode="after")
    def _check_security_rules(self) -> Self:
        if len(self.jwt_secret.get_secret_value()) < JWT_SECRET_MIN_LENGTH:
            raise ValueError(f"JWT_SECRET debe tener al menos {JWT_SECRET_MIN_LENGTH} caracteres")
        if self.environment == "production":
            if not self.cookie_secure:
                raise ValueError("En producción COOKIE_SECURE debe ser true (HTTPS obligatorio)")
            if self.database_url.get_secret_value().startswith("sqlite"):
                raise ValueError("En producción DATABASE_URL debe apuntar a PostgreSQL")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def docs_are_enabled(self) -> bool:
        """Docs activas en desarrollo; en producción solo si DOCS_ENABLED=true."""
        return self.docs_enabled if self.docs_enabled is not None else not self.is_production


@lru_cache  # la primera llamada lee el .env; las siguientes devuelven el mismo objeto
def get_settings() -> Settings:
    """Devuelve la configuración (singleton cacheado)."""
    return Settings()  # type: ignore[call-arg]  # los valores vienen del entorno, no de argumentos
