"""Capa INFRASTRUCTURE — adaptadores de SALIDA (implementan los puertos).

Subpaquetes:
- ``wialon/``: integración con la API de Wialon (cliente HTTP, errores y, más
  adelante, gateway, mappers y modelos crudos).
- ``db/`` (próximas metas): SQLAlchemy, sesión y repositorios.

Puede importar: ``app.application`` (puertos), ``app.domain``, ``app.core`` y
cualquier librería externa (httpx, sqlalchemy...). Es el ÚNICO lugar donde viven.
NO la puede importar: ``app.domain`` ni ``app.application`` (lo verifica import-linter).

¿Por qué? Los detalles técnicos (protocolos, formatos, SQL) cambian; el negocio
no. Aislarlos aquí hace que un cambio de proveedor no toque los casos de uso.
"""
