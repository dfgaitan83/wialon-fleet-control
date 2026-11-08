"""Capa DOMAIN — entidades y reglas de negocio PURAS.

Contendrá: ``vehicle.py``, ``driver.py``, ``passenger.py``, ``permissions.py``,
``status.py`` (ej. regla "vehículo detenido si velocidad = 0 por más de N minutos").

Puede importar: SOLO la librería estándar (dataclasses, enum, datetime...).
NO puede importar: httpx, sqlalchemy, fastapi, pydantic_settings, ni ninguna otra
capa de ``app`` (ni siquiera ``application``).

¿Por qué? El dominio es el centro del hexágono: describe el negocio (qué es un
vehículo, cuándo está detenido) sin saber de dónde vienen los datos ni cómo se
muestran. Ejemplo: ``Vehicle.speed_kmh`` siempre está en km/h; la conversión
desde mph (``mu`` 1 o 2 de Wialon) es responsabilidad del mapper en infraestructura.
Lo verifican los contratos "Capas" y "Dominio y aplicación sin infraestructura".
"""
