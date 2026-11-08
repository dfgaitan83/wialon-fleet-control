"""Adaptador Wialon (infraestructura).

Módulos actuales:
- ``client.py``: sesión única, re-login con ``asyncio.Lock``, reintento ante
  sesión expirada y flags en decimal (Meta M1).
- ``errors.py``: ``WialonError`` y códigos de error de Wialon.

Próximos módulos:
- ``gateway.py``: implementa el puerto ``FleetGateway``; captura ``WialonError``
  y la traduce a una excepción de la aplicación.
- ``mappers.py``: dict crudo de Wialon -> entidad de dominio (``pos.y`` -> lat,
  ``mu`` -> conversión a km/h, ``jp`` -> campos personalizados).
- ``raw_models.py``: modelos pydantic del JSON crudo, validados contra
  las fixtures de ``tests/fixtures/wialon/``.

Es el ÚNICO paquete que sabe que existe Wialon.
"""
