/**
 * Errores de la API en formato Problem Details (RFC 9457).
 *
 * ¿Qué es Problem Details? Un formato ESTÁNDAR de error HTTP en JSON:
 *   { "type": "...", "title": "Vehículo no encontrado", "status": 404, "detail": "..." }
 * El backend (app/core/errors.py) responderá SIEMPRE así. Gracias a eso el
 * frontend tiene UNA sola forma de leer errores, venga de donde venga.
 *
 * ¿Por qué una clase ApiError propia? Axios lanza errores con formas distintas
 * (sin red, timeout, 4xx, 5xx...). El interceptor de client.ts los convierte
 * TODOS en ApiError, así los componentes solo manejan un tipo:
 *   catch (e) { if (e instanceof ApiError) mostrar(e.message) }
 */
import { isAxiosError } from 'axios'
import { z } from 'zod'

// Esquema zod del cuerpo Problem Details. Se VALIDA en lugar de confiar en el
// servidor: si un proxy devuelve HTML o un JSON distinto, no rompemos la UI.
const problemSchema = z.object({
  type: z.string().default('about:blank'), // URI que identifica el tipo de error
  title: z.string(), // resumen corto y legible del problema
  status: z.number().int(), // mismo código que el HTTP status
  detail: z.string().optional(), // explicación específica de ESTE caso
  instance: z.string().optional(), // ruta/recurso donde ocurrió
  // Extensión para errores de validación de formularios: { campo: [mensajes] }
  errors: z.record(z.string(), z.array(z.string())).optional(),
})

export type ProblemDetails = z.infer<typeof problemSchema> // tipo derivado del esquema: una sola fuente de verdad

// status 0 = no hubo respuesta HTTP (sin red, CORS, servidor apagado, timeout).
export const NETWORK_ERROR_STATUS = 0

// Mensajes en español para cuando el servidor no envía un Problem Details válido.
const FALLBACK_MESSAGES: Readonly<Record<number, string>> = {
  [NETWORK_ERROR_STATUS]: 'No se pudo conectar con el servidor. Revisa tu conexión.',
  400: 'La solicitud no es válida.',
  401: 'Tu sesión expiró. Inicia sesión de nuevo.',
  403: 'No tienes permiso para realizar esta acción.',
  404: 'El recurso solicitado no existe.',
  409: 'El recurso cambió mientras lo editabas. Recarga e inténtalo de nuevo.',
  422: 'Revisa los datos del formulario.',
  429: 'Demasiadas solicitudes. Espera un momento.',
  503: 'El proveedor GPS no está disponible en este momento.',
}
const DEFAULT_MESSAGE = 'Ocurrió un error inesperado.'

/** Error único de la API que reciben los componentes. */
export class ApiError extends Error {
  readonly status: number // código HTTP (0 si no hubo respuesta)
  readonly problem: ProblemDetails | null // cuerpo Problem Details si llegó y era válido

  constructor(status: number, message: string, problem: ProblemDetails | null = null) {
    super(message) // message = texto listo para mostrar al usuario
    this.name = 'ApiError'
    this.status = status
    this.problem = problem
  }

  /** true si el fallo fue de red (nunca llegó respuesta del servidor). */
  get isNetworkError(): boolean {
    return this.status === NETWORK_ERROR_STATUS
  }

  /** Errores por campo (formularios): { email: ['Formato inválido'] }. */
  get fieldErrors(): Readonly<Record<string, string[]>> {
    return this.problem?.errors ?? {}
  }
}

function fallbackMessage(status: number): string {
  return FALLBACK_MESSAGES[status] ?? DEFAULT_MESSAGE
}

/**
 * Convierte CUALQUIER error (de axios o no) en ApiError.
 * Prioridad del mensaje: detail del servidor > title del servidor > mensaje por defecto.
 */
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error // ya normalizado: no envolver dos veces

  if (!isAxiosError(error)) {
    // Error de programación u otro origen: no exponer detalles internos al usuario.
    return new ApiError(NETWORK_ERROR_STATUS, DEFAULT_MESSAGE)
  }

  const status = error.response?.status ?? NETWORK_ERROR_STATUS // sin response = fallo de red
  const parsed = problemSchema.safeParse(error.response?.data) // safeParse NO lanza excepción
  const problem = parsed.success ? parsed.data : null
  const message = problem?.detail ?? problem?.title ?? fallbackMessage(status)
  return new ApiError(status, message, problem)
}
