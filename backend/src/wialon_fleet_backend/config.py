from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración leída desde variables de entorno o backend/.env (nunca se versiona)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    wialon_token: str
    wialon_base_url: str = "https://hst-api.wialon.com/wialon/ajax.html"
    cors_origins: list[str] = ["http://localhost:5173"]


def get_settings() -> Settings:
    return Settings()
