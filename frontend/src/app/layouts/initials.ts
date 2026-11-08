/** Iniciales para el avatar: "Ana María Gómez" -> "AM". Función pura (fácil de probar). */
export function initials(fullName: string): string {
  return fullName
    .split(/\s+/) // separa por espacios (uno o varios)
    .filter(Boolean) // descarta vacíos (espacios al inicio/fin)
    .slice(0, 2) // máximo dos letras
    .map((word) => word[0]?.toUpperCase() ?? '')
    .join('')
}
