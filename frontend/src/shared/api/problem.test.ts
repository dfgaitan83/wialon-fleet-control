import { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from 'axios'
import { describe, expect, it } from 'vitest'

import { ApiError, NETWORK_ERROR_STATUS, toApiError } from './problem'

const config = { headers: new AxiosHeaders() } as InternalAxiosRequestConfig

/** Crea un AxiosError con respuesta HTTP simulada. */
function httpError(status: number, data: unknown): AxiosError {
  const response = { status, data, statusText: '', headers: {}, config }
  return new AxiosError('fail', AxiosError.ERR_BAD_RESPONSE, config, null, response)
}

describe('toApiError', () => {
  it('usa el "detail" del Problem Details como mensaje para el usuario', () => {
    const problem = { type: 'about:blank', title: 'No encontrado', status: 404, detail: 'El vehículo 9 no existe' }

    const error = toApiError(httpError(404, problem))

    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(404)
    expect(error.message).toBe('El vehículo 9 no existe')
    expect(error.problem?.title).toBe('No encontrado')
  })

  it('expone los errores por campo de formularios (422)', () => {
    const problem = { title: 'Datos inválidos', status: 422, errors: { email: ['Formato inválido'] } }

    const error = toApiError(httpError(422, problem))

    expect(error.fieldErrors).toEqual({ email: ['Formato inválido'] })
  })

  it('usa un mensaje en español si el cuerpo NO es Problem Details (ej. HTML de un proxy)', () => {
    const error = toApiError(httpError(503, '<html>Bad gateway</html>'))

    expect(error.problem).toBeNull()
    expect(error.message).toBe('El proveedor GPS no está disponible en este momento.')
  })

  it('marca como error de red cuando no hubo respuesta del servidor', () => {
    const error = toApiError(new AxiosError('Network Error', AxiosError.ERR_NETWORK, config))

    expect(error.status).toBe(NETWORK_ERROR_STATUS)
    expect(error.isNetworkError).toBe(true)
  })

  it('no expone detalles internos de errores que no vienen de axios', () => {
    const error = toApiError(new TypeError('x is undefined'))

    expect(error.message).toBe('Ocurrió un error inesperado.')
  })

  it('no vuelve a envolver un ApiError existente', () => {
    const original = new ApiError(409, 'Conflicto')

    expect(toApiError(original)).toBe(original)
  })
})
