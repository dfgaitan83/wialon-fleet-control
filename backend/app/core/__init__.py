"""Capa CORE — utilidades transversales.

Contiene: ``config.py`` (settings desde .env) y, en próximas metas,
``security.py``, ``logging.py`` y ``errors.py`` (respuestas Problem Details, RFC 9457).

Puede importar: librería estándar, pydantic / pydantic-settings.
NO puede importar: ``app.api``, ``app.application``, ``app.infrastructure``.
¿Por qué? Todas las capas dependen de core; si core dependiera de ellas se
crearía un ciclo de imports. Lo verifica import-linter (contrato "core independiente").
"""
