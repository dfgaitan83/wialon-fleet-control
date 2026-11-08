"""Capa API — adaptador de ENTRADA HTTP (FastAPI).

Contendrá:
- ``deps.py``: inyección de dependencias (``get_current_user``,
  ``require_permission("drivers:write")``).
- ``v1/``: routers y schemas (DTOs de respuesta), versionados en /api/v1.

Puede importar: ``app.application``, ``app.domain``, ``app.core``, fastapi, pydantic.
Responsabilidad: traducir HTTP <-> casos de uso (validar entrada, llamar al
servicio, convertir la entidad en DTO). NO contiene reglas de negocio.

¿Por qué? Si la lógica viviera en los routers, no se podría reutilizar ni
probar sin levantar el servidor HTTP.
"""
