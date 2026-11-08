"""Capa APPLICATION — casos de uso y puertos.

Contendrá:
- ``ports/``: interfaces (``typing.Protocol``) que la aplicación NECESITA, por
  ejemplo ``FleetGateway`` ("dame los vehículos"), ``UserRepository``, ``AuditRepository``.
- ``services/``: casos de uso (``VehicleService``, ``DriverService``,
  ``PassengerService``, ``AuthService``...) que orquestan dominio + puertos.

Puede importar: ``app.domain``, ``app.core``, librería estándar.
NO puede importar: httpx, sqlalchemy, fastapi, ``app.infrastructure``, ``app.api``.

¿Por qué? Inversión de dependencias: la aplicación DEFINE el puerto y la
infraestructura lo IMPLEMENTA. Así ``VehicleService`` recibe "algo que cumple
FleetGateway" y no sabe si detrás está Wialon real o un fake de los tests.

Trampa a evitar: tampoco se puede capturar ``WialonError`` aquí. El gateway de
infraestructura la traduce a una excepción propia de la aplicación.
"""
