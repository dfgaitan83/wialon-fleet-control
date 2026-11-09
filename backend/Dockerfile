# =============================================================================
# Imagen de producción del backend (Render, DEP-05). Construir desde backend/:
#   docker build -t wialon-fleet-api .
#
# Al arrancar el contenedor:
#   1) alembic upgrade head          -> crea/actualiza las tablas (idempotente)
#   2) python -m scripts.seed_admin  -> crea el Admin inicial si no existe (idempotente)
#   3) uvicorn ...                   -> sirve la API en $PORT (Render lo define)
# Si 1) o 2) fallan (p. ej. falta ADMIN_PASSWORD), el contenedor NO arranca: fail fast.
# =============================================================================
FROM python:3.13-slim

# Sin .pyc sueltos, logs sin buffer (se ven en tiempo real en Render) y uv sin
# descargar otro Python: usa el de la imagen.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# uv fijado a la MISMA versión que generó uv.lock (reproducible).
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv

WORKDIR /app

# Dependencias primero (capa cacheada mientras no cambie el lockfile).
# --locked: falla si uv.lock no coincide con pyproject (SEG-06/08); --no-dev: sin pytest, ruff...
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

# Solo lo necesario para ejecutar (sin tests, fixtures, .env ni BD local: ver .dockerignore).
COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts
COPY app ./app

# Mínimo privilegio: el proceso NO corre como root dentro del contenedor.
RUN useradd --create-home --uid 10001 appuser
USER appuser

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

# --proxy-headers: la IP real del cliente llega en X-Forwarded-For (proxy de Render/Vercel);
# la usan el rate limit y la auditoría. exec: uvicorn recibe las señales de apagado.
CMD ["sh", "-c", "alembic upgrade head && python -m scripts.seed_admin && exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
