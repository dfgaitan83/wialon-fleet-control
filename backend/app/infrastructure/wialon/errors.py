"""Errores de la integración con Wialon (capa de infraestructura).

¿Por qué en un módulo aparte?
- Lo usan el cliente (que los lanza), los scripts y, más adelante, el gateway.
- REGLA HEXAGONAL: ``WialonError`` es un detalle de infraestructura. Ningún
  servicio de ``app.application`` puede capturarla (eso lo acoplaría a Wialon,
  aunque no importe httpx). El futuro ``gateway.py`` la capturará y la traducirá
  a una excepción propia de la aplicación (p. ej. ``FleetProviderUnavailable``),
  que ``core/errors.py`` convertirá en una respuesta Problem Details.
  import-linter lo garantiza: ver ``[tool.importlinter]`` en pyproject.toml.
"""

# ---------------------------------------------------------------------------
# Códigos de error
# ---------------------------------------------------------------------------
ERROR_INVALID_SESSION = 1  # sesión expirada o inválida -> el cliente la renueva automáticamente
ERROR_INVALID_RESULT = 3  # la respuesta no se pudo interpretar (ej. HTML en vez de JSON)
ERROR_ACCESS_DENIED = 7  # sin permiso... o el id NO EXISTE (verificado: Wialon responde 7 a ambos)
ERROR_NETWORK = -1  # código PROPIO (no de Wialon): fallo de red/HTTP antes de recibir JSON

# Traducción al español de los códigos de error documentados por Wialon.
WIALON_ERRORS: dict[int, str] = {
    ERROR_INVALID_SESSION: "Sesión inválida o expirada",
    2: "Nombre de servicio inválido",  # svc mal escrito
    ERROR_INVALID_RESULT: "Resultado inválido", # ej. Wialon devuelve HTML en vez de JSON
    4: "Parámetros de entrada inválidos",  # ej. WRONG_TOKEN_LENGTH (token de 71 chars)
    5: "Error al ejecutar la solicitud",
    6: "Error desconocido",#error 6: "Error desconocido",  # Wialon no documenta este error
    ERROR_ACCESS_DENIED: "Acceso denegado",  # sin permiso sobre el objeto (o el objeto no existe)
    8: "Usuario o contraseña inválidos (o token inválido/expirado)",
    9: "Servidor de autorización no disponible",
    10: "Se alcanzó el límite de solicitudes concurrentes",
    1001: "No hay mensajes en el intervalo seleccionado",
    1002: "Ya existe un elemento con esa propiedad única",  # p. ej. teléfono de conductor repetido (verificado)
    1003: "Solo se permite una solicitud a la vez",  # por eso el explorador va secuencial
    1011: "La IP cambió o la sesión expiró",
}


# ---------------------------------------------------------------------------
# Jerarquía de errores
# ---------------------------------------------------------------------------
class WialonError(Exception):
    """Error base de Wialon (código de la API) o de comunicación (``ERROR_NETWORK``).

    Todas las subclases heredan de aquí (Liskov): quien capture ``WialonError``
    sigue atrapando cualquier fallo de Wialon. Las subclases existen para que el
    gateway reaccione por TIPO (``except WialonUnavailable`` -> 503) en vez de
    comparar códigos numéricos repartidos por el código.
    """

    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"Wialon error {code}: {message}")  # texto legible en logs/consola
        self.code = code  # código numérico original (se conserva para logs y decisiones)
        self.message = message  # descripción en español o el "reason" de Wialon


class WialonSessionError(WialonError):
    """No hay sesión válida: expiró (1, 1011) o el token es inválido/expiró (8)."""


class WialonAccessDenied(WialonError):
    """El token no tiene permiso sobre el objeto (7) -> en la API pública: 403."""


class WialonNotFound(WialonError):
    """El objeto pedido no existe o no es visible para el token -> 404.

    Wialon NO tiene código propio de "no encontrado": responde 7 tanto si el id
    no existe como si no hay permiso (verificado con ``core/search_item``). Por
    eso esta clase NO está en la tabla de códigos: la lanza el cliente en las
    búsquedas por id (``WialonClient.search_item``), igual que GitHub responde
    404 a un repositorio privado para no revelar que existe.
    """


class WialonConflict(WialonError):
    """Propiedad única repetida (1002): p. ej. el teléfono de un conductor ya lo usa otro -> 409."""


class WialonUnavailable(WialonError):
    """Wialon no responde o está saturado: red/timeout/5xx, respuesta no JSON, 9, 10, 1003.

    Es un fallo TEMPORAL del proveedor -> en la API pública: 503 "intenta más tarde".
    """


# Tabla código -> subclase. Abierto/cerrado: soportar un código nuevo es añadir
# UNA línea aquí, sin tocar ``error_from_code`` ni el cliente.
_ERROR_TYPES: dict[int, type[WialonError]] = {
    ERROR_INVALID_SESSION: WialonSessionError,
    8: WialonSessionError,
    1011: WialonSessionError,
    ERROR_ACCESS_DENIED: WialonAccessDenied,
    1002: WialonConflict,
    ERROR_NETWORK: WialonUnavailable,
    ERROR_INVALID_RESULT: WialonUnavailable,
    9: WialonUnavailable,
    10: WialonUnavailable,
    1003: WialonUnavailable,
}


def error_from_code(code: int, message: str) -> WialonError:
    """Fábrica: crea la subclase que corresponde al código (``WialonError`` si no hay)."""
    return _ERROR_TYPES.get(code, WialonError)(code, message)
