"""Punto de entrada de la API FastAPI.

Arranque en desarrollo (desde backend/):
    python -m uv run fastapi dev app/main.py   ->  http://localhost:8000/docs
"""

from collections.abc import AsyncIterator  # tipo del generador del lifespan
from contextlib import asynccontextmanager  # convierte la función en "arranque/apagado"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.services.wialon_client import WialonClient

settings = get_settings()  # se valida la configuración al importar: falla rápido si falta el token


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Ciclo de vida de la app: lo de antes de ``yield`` corre al arrancar, lo de después al apagar.

    ¿Por qué aquí? Requisito "una sola sesión Wialon en toda la app": se crea UNA
    instancia del cliente y se guarda en ``app.state``; todas las rutas la
    comparten en lugar de crear su propio cliente (y su propia sesión).
    """
    app.state.wialon = WialonClient(  # instancia única compartida por todas las rutas
        settings.wialon_base_url,
        settings.wialon_token.get_secret_value(),  # único lugar donde se "abre" el secreto
        settings.wialon_timeout_seconds,
    )
    # No se hace login aquí (login perezoso): el servidor arranca aunque Wialon esté caído.
    try:
        yield  # la aplicación atiende peticiones mientras está "pausada" aquí
    finally:
        await app.state.wialon.close()  # al apagar: logout en Wialon y cierre de conexiones


app = FastAPI(title="Wialon Fleet Control API", lifespan=lifespan)

# CORS: el navegador bloquea llamadas del frontend (localhost:5173) a otro puerto (8000)
# salvo que el backend lo permita explícitamente. Solo se abren los orígenes configurados.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # lista blanca, nunca "*"
    allow_methods=["GET", "POST"],  # solo los métodos que usa la app
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Comprobación de vida del servidor (no consulta Wialon)."""
    return {"status": "ok"}
