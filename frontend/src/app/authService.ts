/**
 * Elige QUÉ implementación del puerto AuthService usa la app (raíz de composición).
 *
 * - `npm run dev`      -> authApi (HTTP real contra el backend).
 * - `npm run dev:demo` -> demoAuthService (en memoria), solo para revisar la UI
 *                         mientras el backend no tiene /auth/login (meta M2).
 * - `npm run build`    -> SIEMPRE authApi: import.meta.env.DEV es false en producción,
 *                         Vite sustituye la condición por `false` y elimina el demo del bundle.
 */
import { authApi } from '@/shared/auth/authApi'
import { demoAuthService } from '@/shared/auth/demoAuthService'
import type { AuthService } from '@/shared/auth/types'

/** true solo en el servidor de desarrollo arrancado con `--mode demo`. */
export const IS_DEMO_AUTH = import.meta.env.DEV && import.meta.env.MODE === 'demo'

export const authService: AuthService = IS_DEMO_AUTH ? demoAuthService : authApi
