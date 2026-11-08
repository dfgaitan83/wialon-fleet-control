/**
 * Utilidad de tests: reemplaza la "red" de axios por una función que decide la respuesta.
 * Es el equivalente frontend de httpx.MockTransport del backend: los tests nunca
 * llaman a un servidor real, pero SÍ pasan por los interceptores de verdad.
 */
import {
  AxiosError,
  AxiosHeaders,
  type AxiosAdapter,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios'

import { apiClient } from '@/shared/api/client'

export interface MockReply {
  readonly status: number
  readonly data?: unknown
}

/** Función que recibe la petición (para inspeccionarla) y devuelve la respuesta simulada. */
export type MockHandler = (config: InternalAxiosRequestConfig) => MockReply | 'network-error'

/** Instala el handler en el apiClient real. Devuelve una función para restaurar el adaptador original. */
export function mockApi(handler: MockHandler): () => void {
  const original = apiClient.defaults.adapter
  const adapter: AxiosAdapter = async (config) => {
    const reply = handler(config)
    if (reply === 'network-error') {
      // Sin "response": así se ve en axios un servidor apagado o un fallo de red.
      throw new AxiosError('Network Error', AxiosError.ERR_NETWORK, config)
    }
    const response: AxiosResponse = {
      data: reply.data,
      status: reply.status,
      statusText: String(reply.status),
      headers: new AxiosHeaders(),
      config,
    }
    // axios trata 2xx como éxito; el resto como error con response adjunta.
    if (reply.status >= 200 && reply.status < 300) return response
    throw new AxiosError(`HTTP ${reply.status}`, AxiosError.ERR_BAD_RESPONSE, config, null, response)
  }
  apiClient.defaults.adapter = adapter
  return () => {
    apiClient.defaults.adapter = original
  }
}
