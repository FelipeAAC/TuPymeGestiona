# Verificación final de identidad y mantenedores

Fecha de esta evidencia: **2026-10-21**. La revisión se ejecutó sobre la rama
`codex/identity-maintainers-overhaul`, cuyo punto de partida es el `develop-v2`
limpio (`e484937`).

## Resultados reproducibles en este entorno

| Comprobación | Resultado | Evidencia / limitación |
|---|---|---|
| `python -m compileall -q backend` | PASS | Sintaxis Python compilada sin errores |
| `frontend/npm run typecheck` | PASS | TypeScript principal y `maintainers` sin errores |
| `frontend/npm run build` | PASS | Bundle `frontend/dist/frontend` generado |
| `frontend/npm run build:maintainers` | PASS | Bundle `frontend/dist/maintainers` generado |
| `frontend/npm audit` | **LIMITACIÓN** | El lockfile base reporta 4 vulnerabilidades en `@modelcontextprotocol/server` y `vite`, heredadas de Angular 22.2.1; resolverlas requiere una decisión de actualización y puede introducir cambios mayores |
| `git diff --check` | PASS | Sin errores de whitespace |

## Comprobaciones que requieren Windows/MySQL

No se marcaron como aprobadas porque este entorno no contiene la virtualenv
Windows del proyecto ni Django/DRF/MySQLdb instalados:

```text
backend/.venv/Scripts/python.exe manage.py check
backend/.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
backend/.venv/Scripts/python.exe manage.py migrate --plan
backend/.venv/Scripts/python.exe manage.py test
backend/.venv/Scripts/python.exe -m pip check
```

En Windows, con MySQL activo y `backend/.env` configurado, ejecuta el bloque
anterior desde la raíz. Un fallo de conexión o una migración pendiente debe
resolverse antes de presentar la aplicación. La ausencia de esta herramienta
en el entorno Linux no implica que los comandos Django hayan pasado.

## Matriz manual pendiente de repetir en Windows

Usa cuentas separadas o una base demo limpia y comprueba cada respuesta en la
interfaz y en el backend:

1. `CUSTOMER`: Portal Cliente, recuperación de contraseña y bloqueo de `/app/*`,
   `:4300` y `/api/maintainers/*`.
2. `CUSTOMER` + `COMPANY_ADMIN`: conserva compras y solo ve las empresas de sus
   membresías.
3. `COMPANY_ADMIN`: puede operar su empresa, pero no mantenedores ni otra
   empresa.
4. `PLATFORM_ADMIN`: puede entrar a `http://localhost:4300` y consultar la
   superficie `/api/maintainers/*`; no recibe secretos de SMTP, SII o Mercado
   Pago.
5. Solicita un reset, procesa el outbox de consola y confirma que el enlace
   expira y no se imprime en valores persistidos sin cifrar.

La suite backend existente y las pruebas de regresión incorporadas en los
slices anteriores deben ejecutarse con la virtualenv Windows. El informe de
esta etapa no sustituye esa ejecución.
