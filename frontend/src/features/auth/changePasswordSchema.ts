/**
 * Validación del cambio de contraseña (zod). Refleja la política del backend
 * (backend/app/domain/users.py: password_policy_errors) para avisar ANTES de
 * enviar; el backend vuelve a validar igualmente (nunca confiar solo en el cliente).
 */
import { z } from 'zod'

export const PASSWORD_MIN_LENGTH = 12
export const PASSWORD_MAX_LENGTH = 128

export function changePasswordSchema(email: string) {
  const localPart = email.split('@')[0]?.toLowerCase() ?? ''
  return z
    .object({
      currentPassword: z.string().min(1, 'Ingresa tu contraseña actual'),
      newPassword: z
        .string()
        .min(PASSWORD_MIN_LENGTH, `Debe tener al menos ${PASSWORD_MIN_LENGTH} caracteres`)
        .max(PASSWORD_MAX_LENGTH, `Debe tener como máximo ${PASSWORD_MAX_LENGTH} caracteres`)
        .refine((value) => /\p{L}/u.test(value) && /\d/.test(value), 'Debe combinar letras y números')
        .refine(
          (value) => localPart.length < 3 || !value.toLowerCase().includes(localPart),
          'No debe contener tu correo',
        ),
      confirmPassword: z.string().min(1, 'Repite la nueva contraseña'),
    })
    .refine((data) => data.newPassword === data.confirmPassword, {
      path: ['confirmPassword'],
      message: 'Las contraseñas no coinciden',
    })
    .refine((data) => data.newPassword !== data.currentPassword, {
      path: ['newPassword'],
      message: 'Debe ser distinta de la contraseña actual',
    })
}

export type ChangePasswordForm = z.infer<ReturnType<typeof changePasswordSchema>>
export type ChangePasswordErrors = Partial<Record<keyof ChangePasswordForm, string>>

/** Valida y devuelve datos limpios o el PRIMER error de cada campo. */
export function validateChangePassword(
  input: ChangePasswordForm,
  email: string,
): { data: ChangePasswordForm } | { errors: ChangePasswordErrors } {
  const result = changePasswordSchema(email).safeParse(input)
  if (result.success) return { data: result.data }
  const errors: ChangePasswordErrors = {}
  for (const issue of result.error.issues) {
    const field = issue.path[0] as keyof ChangePasswordForm
    errors[field] ??= issue.message
  }
  return { errors }
}
