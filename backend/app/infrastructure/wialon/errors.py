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
ERROR_NETWORK = -1  # código PROPIO (no de Wialon): fallo de red/HTTP antes de recibir JSON

# Traducción al español de los códigos de error documentados por Wialon.
WIALON_ERRORS: dict[int, str] = {
    ERROR_INVALID_SESSION: "Sesión inválida o expirada",
    2: "Nombre de servicio inválido",  # svc mal escrito
    3: "Resultado inválido", # ej. Wialon devuelve HTML en vez de JSON
    4: "Parámetros de entrada inválidos",  # ej. WRONG_TOKEN_LENGTH (token de 71 chars)
    5: "Error al ejecutar la solicitud",
    6: "Error desconocido",#error 6: "Error desconocido",  # Wialon no documenta este error
    7: "Acceso denegado",  # el token no tiene permiso sobre ese objeto
    8: "Usuario o contraseña inválidos (o token inválido/expirado)",
    9: "Servidor de autorización no disponible",
    1001: "No hay mensajes en el intervalo seleccionado",
    1003: "Solo se permite una solicitud a la vez",  # por eso el explorador va secuencial
}


class WialonError(Exception):
    """Error de Wialon (código de la API) o de comunicación (``ERROR_NETWORK``).

    Unifica todos los fallos de Wialon en un solo tipo, para que la capa de
    infraestructura (gateway) los traduzca en un único punto.
    """

    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"Wialon error {code}: {message}")  # texto legible en logs/consola
        self.code = code  # código numérico para decidir programáticamente
        self.message = message  # descripción en español o el "reason" de Wialon
