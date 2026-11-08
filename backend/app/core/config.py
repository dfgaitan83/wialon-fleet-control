"""Configuración del backend leída desde variables de entorno / ``backend/.env``.

¿Por qué pydantic-settings?
- Valida tipos al arrancar: si falta ``WIALON_TOKEN`` el servidor NO arranca y
  muestra un error claro (fail fast), en vez de fallar más tarde en una petición.
- Los secretos viven solo en ``.env`` (ignorado por git); en el repo solo está
  ``.env.example`` con valores de ejemplo.
"""

from functools import lru_cache  # para crear Settings una sola vez
from pathlib import Path  # rutas independientes del sistema operativo

from pydantic import SecretStr  # tipo que oculta el valor al imprimirlo
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ruta absoluta a backend/.env calculada desde ESTE archivo (backend/app/core/config.py):
# parents[0] = backend/app/core, parents[1] = backend/app, parents[2] = backend.
# Así el .env se encuentra aunque el proceso se ejecute desde otra carpeta.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Variables de configuración. El nombre del atributo = variable en MAYÚSCULAS.

    Ej.: ``wialon_token`` se lee de ``WIALON_TOKEN``. Las variables de entorno
    del sistema tienen prioridad sobre el archivo .env (útil en despliegue).
    """

    # Indica de qué archivo leer y con qué codificación (tildes/ñ sin problemas).
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8")

    # SecretStr: print(settings) muestra '**********'; el valor real solo se obtiene
    # explícitamente con .get_secret_value(). Evita filtrar el token en logs.
    wialon_token: SecretStr  # obligatorio (sin valor por defecto)
    wialon_base_url: str = "https://hst-api.wialon.com/wialon/ajax.html"  # endpoint único
    wialon_timeout_seconds: float = 15.0  # tiempo máximo por petición a Wialon
    # Orígenes que pueden llamar al backend desde el navegador (5173 = puerto de Vite).
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache  # la primera llamada lee el .env; las siguientes devuelven el mismo objeto
def get_settings() -> Settings:
    """Devuelve la configuración (singleton cacheado)."""
    return Settings()  # type: ignore[call-arg]  # los valores vienen del entorno, no de argumentos
