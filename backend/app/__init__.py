"""Backend Wialon Fleet Control — arquitectura por capas, estilo hexagonal ligero.

Mapa de capas (las flechas indican "puede importar a")::

        api  ──────►  application  ──────►  domain
         │               ▲   (define puertos = Protocols)
         │               │
         │        infrastructure  (implementa los puertos: Wialon, BD)
         │               │
         └──── main.py ──┘   raíz de composición: crea y conecta todo

    core: transversal (config, logging, errores); cualquiera puede usarlo.

LA REGLA (la que se defiende en la sustentación):
    Ningún servicio de ``application`` ni entidad de ``domain`` importa httpx,
    SQLAlchemy, FastAPI ni nada de Wialon. Solo conocen interfaces (puertos).

¿Por qué?
- Se puede probar la lógica de negocio con implementaciones falsas de los
  puertos, sin red ni base de datos.
- Si mañana cambia el proveedor GPS o la BD, solo cambia ``infrastructure``.

¿Cómo se garantiza? No es una promesa: lo verifica ``import-linter``
(contratos en ``[tool.importlinter]`` de pyproject.toml). Comando:
    python -m uv run lint-imports
"""
