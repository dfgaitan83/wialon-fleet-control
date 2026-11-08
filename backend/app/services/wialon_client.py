"""Cliente asíncrono para la API Remote de Wialon (endpoint único ``ajax.html``).

Meta M1 — Conexión con Wialon.

Cómo funciona la API de Wialon
------------------------------
Wialon no es una API REST clásica: todas las operaciones van por POST al MISMO
endpoint (``.../wialon/ajax.html``) y se distinguen por el parámetro ``svc``
(nombre del servicio). Los parámetros viajan como un JSON serializado dentro del
campo de formulario ``params``. Ejemplo de cuerpo enviado::

    svc=core/search_items&params={"spec": {...}, "flags": 5385}&sid=<id de sesión>

Flujo de sesión::

    token/login  ──►  Wialon responde "eid" (= sid, id de sesión)
         │
         ▼
    core/search_items, etc. (cada llamada lleva &sid=<eid>)
         │
         ▼
    core/logout  (libera la sesión en el servidor)

Wialon NO usa códigos HTTP para los errores: responde HTTP 200 con un cuerpo
``{"error": N}``. Por eso el cliente inspecciona el JSON y lo convierte en
``WialonError`` (ver ``WIALON_ERRORS``).

Decisiones de diseño 
-------------------------------------
1. **Sesión única por aplicación.** ``app/main.py`` crea UNA sola instancia de
   este cliente al arrancar FastAPI; todas las peticiones la comparten.
2. **Login perezoso (lazy).** El login ocurre en la primera llamada real, no al
   arrancar, para que el backend levante aunque Wialon esté caído.
3. **Re-login protegido con ``asyncio.Lock``.** Si la sesión expira y llegan
   muchas peticiones a la vez, solo UNA hace login; las demás reutilizan la
   sesión nueva. Ver ``ensure_session``.
4. **Reintento único ante sesión expirada** (error 1), para no entrar en bucles.
5. **Flags en decimal**, con su equivalente hexadecimal en el comentario.
6. **Sin caché**: la cuenta demoApps es compartida y sus datos cambian.
7. **Timestamps en Unix UTC**: la conversión a America/Bogota la hace el frontend.
8. **Nunca filtrar secretos**: ``token/login`` devuelve el token EN CLARO (``th``);
   se elimina con ``SENSITIVE_LOGIN_KEYS`` antes de exponer la respuesta.

Documentación oficial: https://sdk.wialon.com/wiki/en/sidebar/remoteapi/apiref/apiref
"""

import asyncio  # Lock para proteger el login entre tareas concurrentes
import json  # Wialon recibe "params" como texto JSON, no como campos sueltos
import logging  # registro de eventos (nunca se registran token ni sid)
from dataclasses import dataclass  # para la sesión inmutable (frozen=True)
from typing import Any, Self  # Self = tipo de retorno de __aenter__

import httpx  # cliente HTTP asíncrono (no bloquea el event loop de FastAPI)

# Logger con el nombre del módulo: permite filtrar los logs de Wialon por separado.
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Códigos de error
# ---------------------------------------------------------------------------
ERROR_INVALID_SESSION = 1  # sesión expirada o inválida -> se renueva automáticamente
ERROR_NETWORK = -1  # código PROPIO (no de Wialon): fallo de red/HTTP antes de recibir JSON

# Traducción al español de los códigos de error documentados por Wialon.
WIALON_ERRORS: dict[int, str] = {
    ERROR_INVALID_SESSION: "Sesión inválida o expirada",
    2: "Nombre de servicio inválido",  # svc mal escrito
    3: "Resultado inválido",
    4: "Parámetros de entrada inválidos",  # ej. WRONG_TOKEN_LENGTH (token de 71 chars)
    5: "Error al ejecutar la solicitud",
    6: "Error desconocido",
    7: "Acceso denegado",  # el token no tiene permiso sobre ese objeto
    8: "Usuario o contraseña inválidos (o token inválido/expirado)",
    9: "Servidor de autorización no disponible",
    1001: "No hay mensajes en el intervalo seleccionado",
    1003: "Solo se permite una solicitud a la vez",  # por eso el explorador va secuencial
}

# ---------------------------------------------------------------------------
# Flags de unidades (avl_unit = vehículos). Decimal (hex en el comentario).
# Cada flag pide un "bloque" de propiedades; se SUMAN para pedir varios a la vez.
# ---------------------------------------------------------------------------
UNIT_FLAG_BASE = 1  # 0x1: id, nm (nombre), mu (unidades de medida), uacl (permisos)
UNIT_FLAG_CUSTOM_FIELDS = 8  # 0x8: campos personalizados (flds)
UNIT_FLAG_ADVANCED = 256  # 0x100: propiedades avanzadas (uid/IMEI, ph/teléfono, hw)
UNIT_FLAG_LAST_MESSAGE_POSITION = 1024  # 0x400: lmsg y pos (lat, lon, velocidad, rumbo, hora)
UNIT_FLAG_SENSORS = 4096  # 0x1000: sensores configurados (sens)
UNIT_FLAGS_EXPLORE = (  # todos los bloques que necesita el explorador M1
    UNIT_FLAG_BASE
    + UNIT_FLAG_CUSTOM_FIELDS
    + UNIT_FLAG_ADVANCED
    + UNIT_FLAG_LAST_MESSAGE_POSITION
    + UNIT_FLAG_SENSORS
)  # = 5385 (comprobado en test_login_search_and_logout_flow)

# ---------------------------------------------------------------------------
# Flags de recursos (avl_resource). Un "recurso" es el contenedor donde Wialon
# guarda conductores, pasajeros (tags), geocercas, notificaciones, etc.
# ---------------------------------------------------------------------------
RESOURCE_FLAG_BASE = 1  # 0x1: id, nm, mu, uacl
RESOURCE_FLAG_DRIVERS = 256  # 0x100: conductores (clave "drvrs")
RESOURCE_FLAG_DRIVER_GROUPS = 32768  # 0x8000: grupos de conductores ("drvrsgr")
RESOURCE_FLAG_TAGS = 2097152  # 0x200000: pasajeros; Wialon los llama "tags"
RESOURCE_FLAG_TAG_GROUPS = 8388608  # 0x800000: grupos de pasajeros ("tagsgr")
RESOURCE_FLAGS_EXPLORE = (  # todos los bloques de recursos que usa M1
    RESOURCE_FLAG_BASE
    + RESOURCE_FLAG_DRIVERS
    + RESOURCE_FLAG_DRIVER_GROUPS
    + RESOURCE_FLAG_TAGS
    + RESOURCE_FLAG_TAG_GROUPS
)  # = 10518785

# Campos de la respuesta de login que NUNCA deben salir de este cliente.
# frozenset = conjunto inmutable: nadie puede quitar una clave por error en tiempo de ejecución.
SENSITIVE_LOGIN_KEYS = frozenset(
    {
        "eid",  # id de sesión: quien lo tenga opera la cuenta mientras la sesión viva
        "th",  # el token de acceso EN CLARO (hallazgo verificado en demoApps)
        "token",  # metadatos del token (app, permisos, duración)
        "gis_sid",  # sesión de los servicios GIS de Wialon
        "host",  # IP pública desde la que nos conectamos (dato personal)
    }
)


class WialonError(Exception):
    """Error de Wialon (código de la API) o de comunicación (``ERROR_NETWORK``).

    Unifica todos los fallos en un solo tipo: las capas superiores (rutas
    FastAPI, scripts) capturan una sola excepción y deciden según ``code``
    (p. ej. 8 = token inválido -> 401 hacia el frontend).
    """

    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"Wialon error {code}: {message}")  # texto legible en logs/consola
        self.code = code  # código numérico para decidir programáticamente
        self.message = message  # descripción en español o el "reason" de Wialon


@dataclass(frozen=True)  # frozen = inmutable: la sesión se reemplaza, nunca se modifica
class WialonSession:
    """Datos de la sesión activa.

    Al ser inmutable, comparar por ``sid`` es seguro para detectar si otra
    tarea ya renovó la sesión (ver ``ensure_session``).
    """

    sid: str  # id de sesión que se envía en cada llamada (&sid=...)
    user_name: str  # nombre del usuario Wialon (ej. "DemoApps")
    user_id: int  # id numérico del usuario
    raw: dict[str, Any]  # respuesta de login SIN SENSITIVE_LOGIN_KEYS (segura para guardar)


class WialonClient:
    """Cliente de la API de Wialon con sesión única y renovación segura.

    Uso como context manager (scripts)::

        async with WialonClient(base_url, token) as client:
            units = await client.search_items("avl_unit", UNIT_FLAGS_EXPLORE)
        # al salir hace logout y cierra la conexión HTTP

    Uso en la app: una única instancia en ``app.state.wialon`` (ver ``app/main.py``).
    """

    def __init__(
        self,
        base_url: str,  # URL de ajax.html (WIALON_BASE_URL en .env)
        token: str,  # token de acceso (WIALON_TOKEN); nunca se loguea
        timeout_seconds: float = 15.0,  # máximo por petición: no colgar si Wialon no responde
        http_client: httpx.AsyncClient | None = None,  # inyección para tests (MockTransport)
    ) -> None:
        self._base_url = base_url  # "_" = atributo privado: solo lo usa esta clase
        self._token = token
        # Un solo AsyncClient reutiliza conexiones TCP/TLS (keep-alive) -> peticiones más rápidas.
        # Si el test inyecta uno simulado, se usa ese y no se llama a Wialon real.
        self._http = http_client or httpx.AsyncClient(timeout=timeout_seconds)
        self._session: WialonSession | None = None  # None = aún no hay login (login perezoso)
        self._login_lock = asyncio.Lock()  # garantiza un solo login a la vez

    async def __aenter__(self) -> Self:
        # "async with WialonClient(...) as client" entra aquí: hace login y devuelve el cliente.
        await self.ensure_session()
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        # Se ejecuta SIEMPRE al salir del "async with", haya o no excepción -> garantiza logout.
        # *_exc_info recibe (tipo, excepción, traceback); no se usan porque no se suprime el error.
        await self.close()

    @property
    def session(self) -> WialonSession:
        """Sesión actual; lanza ``WialonError`` si todavía no se ha hecho login."""
        if self._session is None:  # se intentó usar la sesión antes del login
            raise WialonError(ERROR_INVALID_SESSION, "No hay sesión activa")
        return self._session

    # ------------------------------------------------------------------
    # HTTP de bajo nivel
    # ------------------------------------------------------------------

    async def _request(self, svc: str, params: dict[str, Any], sid: str | None = None) -> Any:
        """Envía UNA petición a Wialon y traduce cualquier fallo a ``WialonError``.

        No renueva sesión ni reintenta: esa lógica vive en ``call``, así este
        método queda simple y lo pueden usar también login y logout.
        """
        # Cuerpo del formulario: el servicio y sus parámetros serializados como JSON.
        data = {"svc": svc, "params": json.dumps(params)}
        if sid:  # login no lleva sid (todavía no existe); el resto de servicios sí
            data["sid"] = sid
        try:
            # POST application/x-www-form-urlencoded al endpoint único de Wialon.
            response = await self._http.post(self._base_url, data=data)
            response.raise_for_status()  # convierte HTTP 4xx/5xx en excepción
            payload = response.json()  # Wialon siempre debería responder JSON
        except httpx.HTTPError as exc:
            # Red caída, timeout, DNS, HTTP 5xx... Se registra el servicio, NUNCA los datos.
            logger.error("Fallo HTTP llamando a Wialon svc=%s: %s", svc, exc)
            raise WialonError(ERROR_NETWORK, f"No se pudo contactar con Wialon: {exc}") from exc
        except ValueError as exc:
            # El cuerpo no era JSON (ej. página HTML de error de un proxy).
            raise WialonError(3, "Wialon devolvió una respuesta que no es JSON") from exc

        # Wialon reporta errores con HTTP 200 + {"error": N}; "error": 0 significa éxito.
        if isinstance(payload, dict) and payload.get("error", 0) != 0:
            code = int(payload["error"])
            # "reason" lo envía Wialon a veces (ej. WRONG_TOKEN_LENGTH); si no, usamos la tabla.
            reason = payload.get("reason") or WIALON_ERRORS.get(code, "Error no documentado")
            logger.warning("Wialon devolvió error svc=%s code=%s", svc, code)
            raise WialonError(code, reason)
        return payload  # respuesta válida (dict o list según el servicio)

    # ------------------------------------------------------------------
    # Sesión
    # ------------------------------------------------------------------

    async def _login(self) -> WialonSession:
        """Hace ``token/login`` y construye la sesión sin datos sensibles."""
        result = await self._request("token/login", {"token": self._token})  # sin sid
        user = result.get("user", {})  # bloque con datos del usuario autenticado
        return WialonSession(
            sid=result["eid"],  # "eid" es el id de sesión para las siguientes llamadas
            user_name=user.get("nm", ""),  # "nm" = nombre en la nomenclatura de Wialon
            user_id=int(user.get("id", 0)),
            # Copia de la respuesta SIN secretos (token en claro, sid, IP...).
            raw={k: v for k, v in result.items() if k not in SENSITIVE_LOGIN_KEYS},
        )

    async def ensure_session(self, stale_sid: str | None = None) -> WialonSession:
        """Devuelve la sesión activa; hace login solo si no hay o si ``stale_sid`` caducó.

        Ejemplo: 10 peticiones reciben error 1 con sid "A" y todas llaman
        ``ensure_session(stale_sid="A")``. La primera entra al lock y hace login
        (sid "B"). Las otras 9 entran después, ven "B" != "A" y la reutilizan.
        Resultado: 1 solo login (ver ``test_concurrent_calls_login_only_once``).
        """
        async with self._login_lock:  # solo UNA tarea a la vez ejecuta este bloque
            current = self._session  # se lee DENTRO del lock: valor actualizado
            # Hay sesión y no es la que falló -> otra tarea ya la creó/renovó: reutilizar.
            if current is not None and current.sid != stale_sid:
                return current
            # No hay sesión, o la actual es justo la que expiró -> login nuevo.
            self._session = await self._login()
            logger.info("Sesión Wialon iniciada para el usuario %s", self._session.user_name)
            return self._session

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    async def call(self, svc: str, params: dict[str, Any] | None = None) -> Any:
        """Llamada autenticada genérica a cualquier servicio de Wialon.

        Es el ÚNICO punto de entrada que deben usar los servicios de negocio.
        """
        session = await self.ensure_session()  # login perezoso: solo si aún no hay sesión
        try:
            return await self._request(svc, params or {}, sid=session.sid)
        except WialonError as exc:
            if exc.code != ERROR_INVALID_SESSION:  # cualquier error distinto de "sesión expirada"
                raise  # se propaga sin reintentar
            logger.info("Sesión Wialon expirada; renovando")
            # Se pasa el sid que falló para que ensure_session no repita el login
            # si otra tarea concurrente ya lo renovó.
            session = await self.ensure_session(stale_sid=session.sid)
            # Reintento ÚNICO: si vuelve a fallar, el error sube (evita bucles infinitos).
            return await self._request(svc, params or {}, sid=session.sid)

    async def search_items(
        self, items_type: str, flags: int, name_mask: str = "*"
    ) -> list[dict[str, Any]]:
        """Busca elementos con ``core/search_items``.

        Genérico a propósito (sirve para avl_unit, avl_resource, user...) para no
        duplicar la misma llamada en un método por cada tipo.

        Args:
            items_type: ``"avl_unit"`` (vehículos), ``"avl_resource"`` (recursos), ``"user"``...
            flags: suma decimal de flags (p. ej. ``UNIT_FLAGS_EXPLORE``).
            name_mask: filtro por nombre con comodines; ``"*"`` = todos.
        """
        params = {
            "spec": {
                "itemsType": items_type,  # qué tipo de elemento buscar
                "propName": "sys_name",  # buscar por el nombre del elemento
                "propValueMask": name_mask,  # patrón del nombre ("*" = todos)
                "sortType": "sys_name",  # resultados ordenados por nombre
            },
            "force": 1,  # 1 = búsqueda nueva, no reutilizar resultados previos de la sesión
            "flags": flags,  # qué bloques de propiedades devolver por cada elemento
            "from": 0,  # índice inicial
            "to": 0,  # from=0 y to=0 -> devolver TODOS los resultados (sin paginar)
        }
        result = await self.call("core/search_items", params)
        return list(result.get("items", []))  # lista nueva; [] si Wialon no devuelve "items"

    async def logout(self) -> None:
        """Cierra la sesión en Wialon (``core/logout``)."""
        async with self._login_lock:  # evita cerrar mientras otra tarea está haciendo login
            if self._session is None:  # nunca hubo login o ya se cerró: nada que hacer
                return
            sid = self._session.sid  # se guarda el sid para enviarlo a Wialon
            self._session = None  # se "suelta" la sesión local inmediatamente
        # La llamada de red va FUERA del lock para no bloquear otras tareas mientras viaja.
        await self._request("core/logout", {}, sid=sid)

    async def close(self) -> None:
        """Logout + cierre de la conexión HTTP. Nunca lanza excepción."""
        try:
            await self.logout()
        except WialonError as exc:
            # Si la sesión ya expiró, el logout falla: solo se advierte, no debe
            # impedir que la app se apague limpiamente.
            logger.warning("No se pudo cerrar la sesión de Wialon: %s", exc)
        finally:
            await self._http.aclose()  # libera sockets/conexiones TCP siempre
