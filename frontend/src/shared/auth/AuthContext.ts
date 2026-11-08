/**
 * Contexto de React que comparte la sesión con toda la app.
 * Está en un archivo .ts separado del componente AuthProvider.tsx porque
 * react-refresh (recarga en caliente de Vite) exige que los archivos .tsx
 * exporten solo componentes.
 */
import { createContext } from 'react'

import type { AuthContextValue } from './types'

// null por defecto: si alguien usa useAuth() fuera de <AuthProvider>, lo detectamos
// con un error claro (ver useAuth.ts) en lugar de fallar silenciosamente.
export const AuthContext = createContext<AuthContextValue | null>(null)
