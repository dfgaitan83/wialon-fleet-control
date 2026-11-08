/**
 * Validación del formulario de login (zod). Separada del componente (S de SOLID):
 * la regla se prueba sin renderizar nada y el backend vuelve a validar igualmente.
 */
import { z } from 'zod'

export const loginSchema = z.object({
  email: z.string().trim().min(1, 'Ingresa tu correo').pipe(z.email('El correo no es válido')),
  password: z.string().min(1, 'Ingresa tu contraseña'),
})

export type LoginForm = z.infer<typeof loginSchema>
export type LoginFieldErrors = Partial<Record<keyof LoginForm, string>>

/** Valida y devuelve datos limpios o el PRIMER error de cada campo. */
export function validateLogin(input: LoginForm): { data: LoginForm } | { errors: LoginFieldErrors } {
  const result = loginSchema.safeParse(input)
  if (result.success) return { data: result.data }
  const errors: LoginFieldErrors = {}
  for (const issue of result.error.issues) {
    const field = issue.path[0] as keyof LoginForm
    errors[field] ??= issue.message // conserva solo el primer mensaje por campo
  }
  return { errors }
}
