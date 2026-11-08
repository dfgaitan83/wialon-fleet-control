/// <reference types="vite/client" />

// Tipado de las variables de entorno del frontend: import.meta.env.VITE_API_BASE_URL
// deja de ser "any" y TypeScript avisa si se escribe mal el nombre.
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
