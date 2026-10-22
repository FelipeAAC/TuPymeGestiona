# Operación de identidad y mantenedores

Esta guía es el recorrido corto para preparar una instalación local y revisar
la separación entre Portal Cliente, Gestión PYME y la aplicación secundaria de
mantenedores.

## Capacidades de una cuenta

El backend devuelve `access_modes` en `/api/auth/me/` y en el contexto de
organizaciones. Las capacidades se acumulan:

| Capacidad | Destino | Regla de asignación |
|---|---|---|
| `CUSTOMER` | `http://localhost:4200/portal` | Relación de Portal Cliente activa con una tienda; se crea al registrarse con tienda o confirmar el primer pedido |
| `COMPANY_ADMIN` | `http://localhost:4200/app/*` | Membresía activa y permiso `administration.manage` |
| `PLATFORM_ADMIN` | `http://localhost:4300` | `User.platform_admin=true`, otorgado por comando |

Un cliente puede crear una PYME desde `/portal/seller-onboarding`. Ese flujo
conserva `CUSTOMER` y agrega `COMPANY_ADMIN`; no eleva la cuenta a
`PLATFORM_ADMIN`. El selector de aplicación aparece cuando hay más de un modo.

La aplicación de mantenedores y todos sus endpoints están protegidos por
`PLATFORM_ADMIN` en el servidor. Ocultar un enlace en Angular no es una medida
de seguridad. Un `is_superuser` que no tenga `platform_admin=true` se reporta
para revisión, pero no entra automáticamente a mantenedores.

## Preparar cuentas locales

1. Ejecuta las migraciones y crea una cuenta desde `/portal/register` o el
   seed local.
2. Para administrar una PYME, crea la empresa desde el onboarding y verifica
   la membresía resultante.
3. Para el operador general, promueve una cuenta existente explícitamente:

   ```cmd
   pushd backend
   .\.venv\Scripts\python.exe manage.py promote_platform_admin --email operador@ejemplo.local
   popd
   ```

   El comando no crea usuarios, no cambia contraseñas y no altera roles de
   empresa. Es seguro repetirlo.
4. Audita la clasificación antes de una presentación:

   ```cmd
   pushd backend
   .\.venv\Scripts\python.exe manage.py audit_access_modes
   .\.venv\Scripts\python.exe manage.py audit_access_modes --format json > access-modes.json
   popd
   ```

   El informe es de solo lectura. Revisa `ambiguous`, `unclassified` y
   `superusers_without_platform_admin`; borra el JSON local después si contiene
   correos.

## Contraseña olvidada y outbox

Configura en `backend/.env` (sin versionarlo):

```text
PASSWORD_RESET_FRONTEND_BASE_URL=http://localhost:4200/reset-password
PASSWORD_RESET_TIMEOUT=3600
TRANSACTIONAL_EMAIL_ENABLED=true
TRANSACTIONAL_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
TRANSACTIONAL_EMAIL_FROM=no-reply@localhost
```

El formulario `/forgot-password` siempre devuelve la misma respuesta. Para una
prueba local, solicita el enlace y procesa el outbox en la terminal del
backend:

```cmd
.\backend\.venv\Scripts\python.exe backend\manage.py process_transactional_notifications --limit 100
```

Con el backend de consola, el mensaje y su URL se imprimen en esa terminal.
El enlace contiene un token de un solo uso con vencimiento; la notificación
guarda el enlace cifrado. Para SMTP cambia el backend y proporciona el usuario
y la contraseña mediante variables de entorno (`TRANSACTIONAL_EMAIL_*`), nunca
en el repositorio.

Recupera estados que quedaron enviándose durante demasiado tiempo sin reenviar
automáticamente:

```cmd
.\backend\.venv\Scripts\python.exe backend\manage.py transactional_email_recover_stale
```

## Arranque de las aplicaciones

Desde tres terminales en la raíz:

```cmd
pushd backend
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
popd
```

```cmd
pushd frontend
npm start
popd
```

```cmd
pushd frontend
npm run start:maintainers
popd
```

Los orígenes esperados son `http://localhost:4200`,
`http://localhost:4300` y la API en `http://127.0.0.1:8000`. Mantén ambos
orígenes en `DJANGO_CSRF_TRUSTED_ORIGINS`. Si usas un túnel, agrega su dominio
exacto a `DJANGO_ALLOWED_HOSTS` y a `DJANGO_CSRF_TRUSTED_ORIGINS`, reinicia
Django y no reutilices una URL vencida.

## Matriz mínima de revisión

| Cuenta | Debe abrir | Debe bloquear |
|---|---|---|
| Solo `CUSTOMER` | Portal, catálogo, pedidos, recuperación | `/app/*`, `:4300`, `/api/maintainers/*` |
| `CUSTOMER` + `COMPANY_ADMIN` | Portal y empresas autorizadas | Empresas ajenas y mantenedores |
| Solo `COMPANY_ADMIN` | Gestión de sus empresas | Portal si no tiene relación comercial, mantenedores |
| `PLATFORM_ADMIN` | Mantenedores y sus endpoints | Acceso implícito a secretos de SMTP/SII/Mercado Pago |

## Limitaciones conocidas

- La aplicación de mantenedores necesita sesión Django; no es un panel
  independiente con identidad propia.
- Su vista de operaciones expone agregados existentes; el backend aún no
  ofrece detalle transaccional específico para cada pedido o venta.
- Mercado Pago, SMTP y SII permanecen desactivados por defecto y requieren
  credenciales y URLs de entorno autorizadas.
- El seed demo es local y no debe usarse como datos de producción.
