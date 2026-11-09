"""Punto de entrada y RAÍZ DE COMPOSICIÓN (composition root) de la API.

¿Qué es la raíz de composición?
En arquitectura hexagonal, las capas internas (domain, application) solo
conocen interfaces (puertos). ALGUIEN tiene que crear las implementaciones
concretas (cliente Wialon, base de datos, Argon2, JWT) y conectarlas: ese
"alguien" es este archivo, junto con ``app/api/deps.py`` (composición por petición).

Arranque en desarrollo (desde backend/):
    uv run alembic upgrade head          # crea/actualiza las tablas
    uv run python -m scripts.seed_admin  # crea el Admin inicial (lee ADMIN_* del entorno)
    uv run uvicorn app.main:create_app --factory --reload   ->  http://localhost:8000/docs
"""

from collections.abc import AsyncIterator  # tipo del generador del lifespan
from contextlib import asynccontextmanager  # convierte la función en "arranque/apagado"
from datetime import timedelta

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.cookies import CSRF_HEADER
from app.api.errors import register_app_error_handlers
from app.api.middleware import register_middleware
from app.api.v1.auth import build_auth_router
from app.api.v1.fleet import router as fleet_router
from app.api.v1.schemas import HealthOut
from app.api.v1.users import router as users_router
from app.core.clock import utc_now

# Importar infraestructura aquí está PERMITIDO: main.py es la raíz de composición.
from app.core.config import Settings, get_settings
from app.core.errors import register_problem_handlers
from app.core.logging import configure_logging
from app.infrastructure.db.base import create_engine, create_session_factory
from app.infrastructure.security import Argon2PasswordHasher, JwtAccessTokenService
from app.infrastructure.wialon.client import WialonClient
from app.infrastructure.wialon.gateway import WialonFleetGateway

API_V1_PREFIX = "/api/v1"


def _health_router() -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health", response_model=HealthOut, summary="Comprobación de vida (no consulta Wialon)")
    async def health() -> HealthOut:
        return HealthOut(status="ok")

    return router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Factoría de la aplicación: crea y configura una instancia NUEVA de FastAPI.

    ¿Por qué una factoría y no un ``app = FastAPI()`` suelto?
    - Los tests crean apps aisladas con configuración propia (BD temporal, sin .env).
    - Todo el "cableado" (middlewares, routers, manejadores de error) queda en
      un solo lugar y en un orden explícito.
    """
    settings = settings or get_settings()  # sin argumento: se lee backend/.env
    configure_logging(json_output=settings.is_production)
    engine = create_engine(settings.database_url.get_secret_value())

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
        app.state.fleet_gateway = WialonFleetGateway(app.state.wialon, clock=utc_now)  # caché TTL compartida
        try:
            yield  # la aplicación atiende peticiones mientras está "pausada" aquí
        finally:
            await app.state.wialon.close()  # al apagar: logout en Wialon y cierre de conexiones
            await engine.dispose()

    docs = settings.docs_are_enabled  # SEG-05: Swagger apagado en producción por defecto
    app = FastAPI(
        title="Wialon Fleet Control API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs else None,
    )

    # Dependencias compartidas (singletons de la app): las usa app/api/deps.py.
    app.state.settings = settings
    app.state.session_factory = create_session_factory(engine)
    app.state.password_hasher = Argon2PasswordHasher()
    app.state.access_tokens = JwtAccessTokenService(
        settings.jwt_secret.get_secret_value(), timedelta(minutes=settings.access_token_minutes), utc_now
    )
    app.state.lockout = timedelta(minutes=settings.login_lockout_minutes)
    app.state.refresh_ttl = timedelta(days=settings.refresh_token_days)
    limiter = Limiter(key_func=get_remote_address)  # un limitador por app (tests aislados)
    app.state.limiter = limiter  # slowapi lo busca aquí

    register_problem_handlers(app)  # errores genéricos -> Problem Details
    register_app_error_handlers(app)  # errores de negocio -> Problem Details
    register_middleware(app, hsts=settings.is_production)
    # CORS: lista blanca explícita (nunca "*"); credenciales sí, porque la sesión va en cookies.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", CSRF_HEADER],
    )

    app.include_router(_health_router())  # /health (Render health check)
    v1 = APIRouter(prefix=API_V1_PREFIX)
    v1.include_router(_health_router())  # /api/v1/health (a través del proxy de Vercel)
    v1.include_router(build_auth_router(limiter, settings))
    v1.include_router(users_router)  # RF-06: gestión de usuarios (Admin)
    v1.include_router(fleet_router)  # RF-10..13, RF-23: vehículos y dashboard
    app.include_router(v1)
    return app


# Sin "app = create_app()" a nivel de módulo: importar este archivo NO lee el .env
# (los tests y la CI importan create_app con su propia configuración). El servidor
# usa la factoría directamente: uvicorn app.main:create_app --factory
