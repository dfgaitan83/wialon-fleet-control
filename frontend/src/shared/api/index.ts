// Punto de entrada público de shared/api: las features importan desde '@/shared/api'.
export { apiClient, setUnauthorizedHandler } from './client'
export { ApiError, NETWORK_ERROR_STATUS, toApiError, type ProblemDetails } from './problem'
