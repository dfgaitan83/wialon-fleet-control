# Uso de IA en el proyecto

Registro honesto de cómo se usó la inteligencia artificial durante la prueba técnica:
qué se le pidió, qué se verificó y qué errores cometió. Se actualiza en cada meta.

## Herramienta

- **Claude Code** (modelo Claude Opus) como asistente de programación en la terminal de VS Code.
- La IA propone y ejecuta cambios; **cada meta se revisa y aprueba antes del commit**.
  Ningún push a GitHub se hace sin autorización explícita.

## Forma de trabajo

1. Se trabaja **una meta a la vez** (M0 → M11), completa y verificada antes de pasar a la siguiente.
2. Cada cambio se verifica con evidencia: tests, linters, contratos de arquitectura,
   build de producción y, cuando aplica, una ejecución real contra Wialon.
3. Todo el código se documenta en español con el **porqué** de cada decisión,
   para poder sustentarlo.
4. Antes de cada commit se buscan secretos en lo que se va a publicar (token, `.env`, contraseñas).

## Registro por meta

| Meta | Qué hizo la IA | Qué se verificó |
|---|---|---|
| M0 | Reorganizó el monorepo (`backend/` + `frontend/`), `.gitignore` raíz, proyecto `uv`, dependencias del plan y CI en GitHub Actions. | `/health` responde; `npm run dev` levanta; `pip-audit` y `npm audit` revisados. |
| M1 | Cliente Wialon con sesión única, re-login protegido con `asyncio.Lock`, flags en decimal y explorador de solo lectura que genera las fixtures. | Ejecución real contra la cuenta `demoApps` (62 vehículos, 2 recursos); tests unitarios con red simulada. |
| Arquitectura | Estructura hexagonal ligera y contratos de `import-linter`. | Se introdujo una violación a propósito y el linter la detectó con archivo y línea. |
| Frontend 1–2 | Cliente axios, capa de sesión, componentes base, router, layouts y paleta oficial. | 67 tests, `tsc`, ESLint, build y verificación de que el modo demo no llega a producción. |

## Errores de la IA detectados y corregidos

Se documentan porque demuestran que el resultado **no se aceptó a ciegas**:

- **Fuga de datos en las fixtures (incidente, 2026-11-09).** La primera versión del explorador
  solo enmascaraba contraseñas dentro de `jp` y publicó en el repositorio (público) contraseñas
  de dispositivos (`psw`), claves de conductores (`pwd`), teléfonos, documentos de identidad y
  nombres de la cuenta compartida. **Corrección:** regla de enmascarado por nombre de campo
  (secreto → `***`, dato personal → enmascarado parcial, nombres → seudónimos), un test guardia
  (`backend/tests/unit/test_fixtures_sanitized.py`) que falla si vuelve a ocurrir, y reescritura del
  historial de Git para eliminar los datos publicados. **Lección:** antes de versionar datos de un
  sistema externo hay que revisar *todos* sus campos, no solo los evidentes.
- **Regla de unidades de medida equivocada (venía del enunciado de trabajo).** La regla
  "si `mu` ≠ 0, convertir la velocidad" habría corrompido los 62 vehículos: con los datos reales
  se comprobó que `mu = 3` (métrico + galones US) ya reporta km/h. Solo `mu` 1 y 2 usan mph.
- **Condiciones de carrera en el login/logout del frontend.** Dos redirecciones competían entre sí
  (tras el login no se volvía a la página original; al cerrar sesión se iba a `/login` en vez de a la
  landing). Las detectaron los tests de integración del router antes de llegar a producción.
- **Versión de Node para el CI.** Se pidió Node 20, pero Vitest 5 exige Node ≥ 22.12; se comprobó
  en los `engines` de las dependencias y se usó Node 24 (LTS), la misma versión del entorno local.

## Hallazgos verificados contra la API real de Wialon

- `token/login` devuelve el **token en claro** (campo `th`): el cliente lo elimina antes de exponer la respuesta.
- Un objeto inexistente responde **error 7** (acceso denegado), igual que uno sin permiso:
  Wialon no distingue ambos casos para no revelar qué IDs existen.
- Las consultas van en secuencia para evitar el **error 1003** (una solicitud a la vez por sesión).

## Límites y buenas prácticas aprendidas

- El token de Wialon se compartió una vez en el chat con la IA; queda la recomendación de
  **revocarlo al terminar la prueba**. En adelante los secretos solo viven en `backend/.env`.
- La IA no tiene acceso a GitHub fuera de los comandos aprobados; las publicaciones las autoriza la persona.
- Las afirmaciones del README (por ejemplo, principios SOLID con archivo y línea) se verifican contra
  el código real antes de publicarse: no se documenta nada que aún no exista.
