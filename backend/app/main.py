"""Punto de entrada y RAÍZ DE COMPOSICIÓN (composition root) de la API.

¿Qué es la raíz de composición?
En arquitectura hexagonal, las capas internas (domain, application) solo
conocen interfaces (puertos). ALGUIEN tiene que crear las implementaciones
concretas (cliente Wialon, base de datos) y conectarlas: ese "alguien" es este
archivo. Por eso ``main.py`` es el ÚNICO módulo de ``app`` (junto con
``api/deps.py`` en el futuro) que puede importar de todas las capas.

Arranque en desarrollo (desde backend/):
    python -m uv run fastapi dev app/main.py   ->  http://localhost:8000/docs
"""

from collections.abc import AsyncIterator  # tipo del generador del lifespan
from contextlib import asynccontextmanager  # convierte la función en "arranque/apagado"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importar infraestructura aquí está PERMITIDO: main.py es la raíz de composición.
from app.core.config import Settings, get_settings
from app.infrastructure.wialon.client import WialonClient


def create_app(settings: Settings | None = None) -> FastAPI:
    """Factoría de la aplicación: crea y configura una instancia NUEVA de FastAPI.

    ¿Por qué una factoría y no un ``app = FastAPI()`` suelto?
    - Los tests pueden crear apps aisladas con configuración propia
      (``create_app(Settings(wialon_token="x"))``) sin tocar el .env real.
    - Todo el "cableado" (middlewares, routers, manejadores de error) queda en
      un solo lugar y en un orden explícito.
    """
    settings = settings or get_settings()  # sin argumento: se lee backend/.env

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Lo de antes de ``yield`` corre al arrancar; lo de después, al apagar.

        Requisito "una sola sesión Wialon en toda la app": se crea UNA instancia
        del cliente y se guarda en ``app.state``; todas las rutas la comparten.
        """
        app.state.wialon = WialonClient(  # instancia única compartida por todas las rutas
            settings.wialon_base_url,
            settings.wialon_token.get_secret_value(),  # único lugar donde se "abre" el secreto
            settings.wialon_timeout_seconds,
        )
        # Sin login aquí (login perezoso): el servidor arranca aunque Wialon esté caído.
        try:
            yield  # la aplicación atiende peticiones mientras está "pausada" aquí
        finally:
            await app.state.wialon.close()  # al apagar: logout en Wialon y cierre de conexiones

    app = FastAPI(title="Wialon Fleet Control API", lifespan=lifespan)

    # CORS: el navegador bloquea llamadas del frontend (localhost:5173) a otro puerto
    # (8000) salvo que el backend lo permita. Solo se abren los orígenes configurados.
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

    # Aquí se registrarán: routers de app.api.v1 y el manejador de errores de app.core.errors.
    return app


# Instancia que usan `fastapi dev app/main.py` y uvicorn (buscan una variable llamada "app").
app = create_app()
