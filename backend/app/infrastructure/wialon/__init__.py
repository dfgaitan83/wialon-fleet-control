"""Adaptador Wialon (infraestructura).

Módulos actuales:
- ``client.py``: sesión única, re-login con ``asyncio.Lock``, reintento ante
  sesión expirada, timeout de 10 s, tenacity solo para errores de red seguros y
  flags en decimal (Meta M1).
- ``errors.py``: ``WialonError`` y sus subclases (Session, AccessDenied,
  NotFound, Unavailable) con la tabla código -> tipo.
- ``raw_models.py``: modelos Pydantic inmutables del JSON crudo (lista blanca
  de campos, SEG-08), validados contra las fixtures de ``tests/fixtures/wialon/``.

Próximos módulos (M4):
- ``gateway.py``: implementa el puerto ``FleetGateway``; captura ``WialonError``
  y la traduce a una excepción de la aplicación.
- ``mappers.py``: modelo crudo validado -> entidad de dominio (``pos.y`` -> lat,
  ``mu`` -> conversión a km/h, ``jp`` -> campos personalizados).

Es el ÚNICO paquete que sabe que existe Wialon.
"""
