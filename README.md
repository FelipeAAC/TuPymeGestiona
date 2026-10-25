# TuPymeGestiona

TuPymeGestiona es una plataforma web para que pequeñas y medianas empresas
puedan administrar su operación y, al mismo tiempo, vender a sus clientes
desde un portal común.

Una persona tiene una sola cuenta. Con esa cuenta puede comprar en distintas
PYMES, crear su propio negocio y entrar a la gestión de las empresas donde
tiene permisos. El proyecto también incluye una aplicación separada para
mantenedores globales.

La idea no es construir un marketplace gigante. La idea es entregar una base
clara para que una PYME pueda manejar productos, inventario, pedidos, ventas,
clientes, usuarios, permisos y pagos desde un mismo lugar.

## Qué incluye

### Para una PYME

- empresas, sucursales, bodegas y usuarios;
- roles, permisos y membresías por empresa;
- categorías, marcas, productos, variantes y proveedores;
- inventario, movimientos y transferencias;
- clientes, pedidos y estados de pedido;
- ventas derivadas de pedidos y ventas directas POS;
- pagos internos en efectivo y transferencia;
- reportes y dashboard;
- facturación electrónica preparada para el flujo SII;
- Mercado Pago Checkout Pro para probar pagos externos.

### Para un cliente

- registro con una identidad única;
- catálogo de distintas tiendas;
- carrito y creación de pedidos;
- historial de compras;
- pago con Mercado Pago;
- creación posterior de una PYME con la misma cuenta.

### Para el administrador global

La aplicación secundaria de mantenedores permite administrar empresas,
catálogos, usuarios, roles y revisar la auditoría global. Solo entra una cuenta
marcada explícitamente como `PLATFORM_ADMIN`.

## Antes de empezar

Este proyecto está pensado para Windows 10/11 y utiliza tres programas locales:

- Python 3.13 o compatible con Django 6.1;
- MySQL 8.x;
- Node.js 22/24 y npm;
- Git y PowerShell.

Necesitas tener MySQL iniciado antes de ejecutar Django. Si el servicio de
MySQL está apagado, las migraciones y el seed van a fallar aunque el código
esté correcto.

## 1. Descargar el proyecto

Desde una consola:

```cmd
git clone https://github.com/FelipeAAC/TuPymeGestiona.git
cd TuPymeGestiona
git checkout develop-v2
```

Nota: `develop-v2` es la rama que usa el grupo para trabajar y probar los
avances actuales.

## 2. Preparar el backend

Primero crea el entorno virtual. Este entorno guarda las dependencias de
Python separadas de las demás aplicaciones del computador.

```cmd
pushd backend
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
popd
```

Ahora crea el archivo `backend/.env`. No copies secretos reales al repositorio.
Para una instalación local puedes comenzar con esto:

```text
DJANGO_SECRET_KEY=cambia-esta-clave-local
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

DB_ENGINE=mysql
DB_NAME=tupymegestiona
DB_USER=tupymegestiona_app
DB_PASSWORD=tu_password_mysql
DB_HOST=127.0.0.1
DB_PORT=3306

DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:4200,http://127.0.0.1:4200,http://localhost:4300,http://127.0.0.1:4300
DJANGO_SESSION_COOKIE_SECURE=false
DJANGO_CSRF_COOKIE_SECURE=false
DJANGO_SECURE_SSL_REDIRECT=false

MERCADO_PAGO_ENABLED=true
MERCADO_PAGO_ACCESS_TOKEN_ENV=MERCADO_PAGO_ACCESS_TOKEN
MERCADO_PAGO_WEBHOOK_SECRET_ENV=MERCADO_PAGO_WEBHOOK_SECRET
MERCADO_PAGO_ACCESS_TOKEN=REEMPLAZA_CON_ACCESS_TOKEN_DE_PRUEBA
MERCADO_PAGO_WEBHOOK_SECRET=REEMPLAZA_CON_CLAVE_DE_WEBHOOKS
MERCADO_PAGO_API_BASE_URL=https://api.mercadopago.com
MERCADO_PAGO_RETURN_BASE_URL=https://URL_PUBLICA_DEL_FRONTEND
MERCADO_PAGO_WEBHOOK_URL=https://URL_PUBLICA_DEL_BACKEND/api/portal/payments/mercado-pago/webhook/
MERCADO_PAGO_HTTP_TIMEOUT=15
MERCADO_PAGO_USE_SANDBOX_INIT_POINT=false
MERCADO_PAGO_ACCEPT_LIVE_MODE=false
MERCADO_PAGO_TEST_USER_IDS=ID_DEL_SELLER_DE_PRUEBA
```

Mercado Pago está implementado como parte del proyecto. Para probarlo se
necesitan credenciales de prueba y dos URLs HTTPS públicas; más abajo está el
procedimiento completo.

## 3. Crear y poblar la base de datos

### Opción recomendada: base limpia

Si quieres empezar de cero, este comando elimina la base local y la vuelve a
crear. Úsalo solo en tu instalación académica:

```powershell
Get-Content .\database\00_reset_database.sql | mysql -u root -p
```

Si no quieres borrar una base existente, usa solamente:

```powershell
Get-Content .\database\01_create_database.sql | mysql -u root -p
```

Ahora valida Django y aplica las migraciones:

```cmd
pushd backend
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py migrate --noinput
popd
```

Nota: las migraciones crean la estructura y los permisos base. Todavía no hay
empresas, productos ni clientes hasta ejecutar el seed.

Carga el dataset académico:

```powershell
.\database\02_poblar_demo.ps1 -Password "DemoLocal2026!"
```

El seed crea empresas de tecnología, salud y bienestar, hogar,
sustentabilidad y vestuario/taller. Usa productos y marcas de referencia para
que los catálogos tengan sentido al recorrer la aplicación.

También crea estas cuentas locales:

| Tipo | Usuario | Contraseña |
|---|---|---|
| Cliente | `cliente@demo-local-2026.tupyme.local` | `DemoLocal2026!` |
| Propietario de PYME | `owner@demo-local-2026.tupyme.local` | `DemoLocal2026!` |
| Administrador global | `admin@demo-local-2026.tupyme.local` | `DemoLocal2026!` |

Estas credenciales sirven solo para la base demo local. Si usas otro valor en
`--seed`, cambia también el dominio que imprime el comando al final.

El seed es determinista. Si lo ejecutas otra vez con el mismo `--seed` y la
misma cantidad de empresas, no duplica el dataset.

## 4. Levantar las tres aplicaciones

Cada aplicación va en su propia consola. MySQL debe estar iniciado antes de
levantar Django.

Para navegar por la aplicación normalmente necesitas estas tres consolas:

| Consola | Proceso | Puerto | Uso |
|---|---|---:|---|
| 1 | Django | 8000 | API y sesiones |
| 2 | Angular principal | 4200 | Portal cliente y gestión PYME |
| 3 | Angular mantenedores | 4300 | Administración global |

Para probar el pago completo con Mercado Pago debes mantener abiertas además:

| Consola | Proceso | Función |
|---|---|---|
| 4 | `ngrok http 4200` | URL pública de Angular para volver desde Mercado Pago |
| 5 | `npx localtunnel --port 8000 ...` | URL pública del webhook de Django |

Si cierras una de las consolas 4 o 5 durante el pago, el pago puede aprobarse
pero el navegador no podrá volver a la tienda o Mercado Pago no podrá entregar
el webhook.

### Consola 1: backend Django

```cmd
cd /d "C:\ruta\TuPymeGestiona\backend"
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

API local:

```text
http://127.0.0.1:8000/api
```

### Consola 2: aplicación principal

```cmd
cd /d "C:\ruta\TuPymeGestiona\frontend"
npm ci
npm start
```

Aplicación principal:

```text
http://localhost:4200
```

Rutas útiles:

```text
/portal
/login
/portal/account
/portal/seller-onboarding
/app/dashboard
/app/products
/app/inventory
/app/orders
/app/sales
/app/reports
```

### Consola 3: mantenedores

```cmd
cd /d "C:\ruta\TuPymeGestiona\frontend"
npm run start:maintainers
```

Aplicación secundaria:

```text
http://localhost:4300
```

Para entrar aquí usa:

```text
admin@demo-local-2026.tupyme.local
DemoLocal2026!
```

La cuenta de mantenedores utiliza el mismo backend y la misma sesión Django,
pero tiene una capacidad global distinta a la de una PYME normal.

Por seguridad, el seed no activa automáticamente el permiso de eliminación
permanente. Si el grupo necesita probar ese flujo destructivo en la base local,
habilítalo de forma explícita:

```cmd
cd /d "C:\ruta\TuPymeGestiona\backend"
.\.venv\Scripts\python.exe manage.py promote_platform_destructive_admin --email admin@demo-local-2026.tupyme.local
```

Ese comando solo modifica la cuenta global demo y no debe ejecutarse con una
cuenta real o en una base compartida.

Después de ejecutarlo, cierra sesión y vuelve a entrar en la aplicación de
mantenedores. El botón **Eliminar** aparecerá junto a los recursos que el
administrador puede borrar permanentemente.

Para probar este flujo sin tocar el dataset principal:

1. Crea una empresa y una sucursal con nombres que indiquen que son de prueba.
2. Edita ambos registros y comprueba que los cambios se reflejen en pantalla.
3. Elimina primero la sucursal y después la empresa.
4. Revisa el resumen de impacto antes de confirmar.
5. Escribe exactamente la frase que muestra la ventana.
6. Indica el motivo, marca la confirmación y mantén pulsado el botón durante
   cinco segundos.
7. Abre **Auditoría global** y comprueba los eventos de creación, modificación
   y eliminación permanente.

La cuenta administradora funciona normalmente sin esta capacidad especial. La
eliminación permanente se delega solo cuando alguien decide probarla de forma
consciente. Si vuelves a crear la base con `00_reset_database.sql` y ejecutas
el seed, el administrador demo vuelve a quedar sin la capacidad destructiva.

## 5. Probar el proyecto

### Como cliente

1. Entra a `http://localhost:4200`.
2. Inicia sesión con la cuenta cliente.
3. Abre el catálogo.
4. Agrega productos y crea un pedido.
5. Revisa el pedido desde **Mi cuenta**.
6. Si configuraste Mercado Pago, inicia el pago desde ese pedido.

### Como propietario de PYME

1. Cierra sesión y entra con la cuenta propietaria.
2. Abre **Gestionar mi PYME**.
3. Cambia de empresa si la cuenta tiene más de una disponible.
4. Revisa productos, bodegas, inventario, clientes, pedidos, ventas y reportes.

### Como administrador global

1. Abre `http://localhost:4300`.
2. Inicia sesión con la cuenta administradora global.
3. Revisa el contexto, empresas, catálogos, usuarios, roles y auditoría.

## 6. Mercado Pago en modo de prueba

Mercado Pago forma parte del proyecto. Para verificar el pago completo desde
un computador local necesitas:

- una aplicación de Mercado Pago;
- credenciales de prueba;
- un usuario vendedor de prueba;
- un usuario comprador de prueba;
- una URL HTTPS para Angular;
- una URL HTTPS para Django.

### 6.1 Credenciales

En Mercado Pago Developers entra a tu aplicación y abre **Credenciales de
prueba**. Usa el Access Token del vendedor de prueba en `backend/.env`.

No pegues el token en Git, en el README ni en `tupymegestion.sql`.

### 6.2 Exponer Angular

Con Angular ejecutándose en el puerto 4200, abre una cuarta consola y déjala
abierta durante toda la prueba:

```cmd
ngrok http 4200
```

Copia la URL HTTPS que entrega ngrok. Esa URL será la dirección que debes abrir
en el navegador para hacer la prueba de pago. No uses `localhost:4200` para
este flujo.

Ejemplo:

```text
https://wildlife-quail-untagged.ngrok-free.dev
```

En `backend/.env` configura:

```text
MERCADO_PAGO_RETURN_BASE_URL=https://tu-url-ngrok
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,tu-url-ngrok.ngrok-free.dev
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:4200,http://127.0.0.1:4200,https://tu-url-ngrok.ngrok-free.dev
```

La URL gratuita de ngrok puede cambiar. Si cambia, actualiza el `.env` y
reinicia Django. Si aparece `ERR_NGROK_3200`, la consola de ngrok se cerró o
el túnel está fuera de línea.

El `angular.json` del proyecto usa `allowedHosts: ["*"]` únicamente para el
servidor local de desarrollo. Esto permite que cada integrante use su propia
URL temporal de ngrok sin modificar el código de la aplicación. No uses esta
configuración como servidor de producción.

### 6.3 Exponer Django

Con Django ejecutándose en el puerto 8000, abre una quinta consola y déjala
abierta para recibir los webhooks:

```cmd
npx localtunnel --port 8000 --subdomain tu-subdominio --print-requests
```

Si el subdominio está ocupado, usa el que entregue LocalTunnel y cambia la
URL en el `.env`.

```text
MERCADO_PAGO_WEBHOOK_URL=https://tu-url-backend/api/portal/payments/mercado-pago/webhook/
```

Ejemplo:

```text
https://few-jobs-behave.loca.lt/api/portal/payments/mercado-pago/webhook/
```

Agrega el host del frontend público a `DJANGO_ALLOWED_HOSTS` y el origen
público de Angular a `DJANGO_CSRF_TRUSTED_ORIGINS`. Después de modificar
`backend/.env`, reinicia Django.

### 6.4 Orden correcto para probar un pago

1. Inicia MySQL.
2. Inicia Django en el puerto 8000.
3. Inicia Angular en el puerto 4200.
4. Inicia ngrok para el puerto 4200.
5. Inicia LocalTunnel para el puerto 8000.
6. Abre la URL pública de ngrok.
7. Entra con la cuenta cliente y crea un pedido.
8. Pulsa **Pagar con Mercado Pago**.
9. Completa el pago con el usuario comprador de prueba.
10. Vuelve a la tienda y actualiza **Mis pedidos**.

El pedido debe mostrar el pago aprobado. El retorno del navegador ejecuta una
actualización del estado y el webhook deja el registro correspondiente en
Django. No cierres ngrok ni LocalTunnel hasta terminar el retorno y comprobar
el pedido.

### 6.4 Configurar Webhooks

En la configuración de Webhooks de la aplicación de prueba:

1. selecciona el modo de prueba;
2. coloca la URL pública del backend;
3. selecciona el evento **Pagos**;
4. guarda la configuración;
5. copia la clave secreta en `MERCADO_PAGO_WEBHOOK_SECRET`.

No uses `Órdenes comerciales` ni `Order (Mercado Pago)` para este flujo: el
proyecto procesa pagos de Checkout Pro.

### 6.5 Verificar el pago

Después de pagar, el backend debe registrar una petición `POST` al webhook.
Puedes revisar los recibos con:

```cmd
pushd backend
.\.venv\Scripts\python.exe manage.py shell -c "from external_payments.models import MercadoPagoWebhookReceipt; print(list(MercadoPagoWebhookReceipt.objects.order_by('-created_at').values('notification_id','data_id','result','created_at')[:10]))"
popd
```

Un webhook procesado muestra:

```text
result: PROCESSED
```

El retorno del navegador también ejecuta `refresh` para que el estado del
pedido se actualice aunque el usuario vuelva antes de que llegue el webhook.

## 7. Limpiar la base después de las pruebas

Durante las pruebas manuales se pueden crear pedidos de Mercado Pago, empresas
de prueba, sucursales y registros de auditoría. Antes de entregar el proyecto
al resto del grupo, vuelve a generar una base limpia y un dump reproducible.

Este proceso elimina la base local completa y conserva solamente el dataset
académico creado por el seed. Los pedidos demo intencionales del cliente se
mantienen para que se puedan revisar los estados de pedido; desaparecen los
pedidos y pagos creados durante tus pruebas manuales.

Desde la raíz del repositorio ejecuta:

```powershell
Get-Content .\database\00_reset_database.sql | mysql -u root -p
.\database\02_poblar_demo.ps1 -Password "DemoLocal2026!"
.\database\03_generar_tupymegestion_sql.ps1 -MysqlDump "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqldump.exe"
```

Si tu ejecutable de MySQL está en otra carpeta, cambia solamente la ruta de
`-MysqlDump`. El último comando actualiza `database/tupymegestion.sql` con el
esquema y los datos limpios. El seed deja la cuenta global como administrador
de plataforma normal; la capacidad destructiva se habilita después solo con el
comando indicado en la sección de mantenedores.

## 8. Comprobar proyecto y builds

Backend:

```cmd
cd /d "C:\ruta\TuPymeGestiona\backend"
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

Frontend:

```cmd
cd /d "C:\ruta\TuPymeGestiona\frontend"
npm run typecheck
npm run build
npm run build:maintainers
```

Si aparece `No module named django`, no estás usando `backend\.venv`. Si
aparece `npm error Missing script`, revisa que no se hayan pegado dos comandos
en la misma línea.

## 9. Crear el dump SQL completo

Después de limpiar, migrar y poblar la base, ejecuta desde la raíz:

```powershell
.\database\03_generar_tupymegestion_sql.ps1
```

El script genera:

```text
database/tupymegestion.sql
```

El archivo contiene el esquema y los datos de la base demo, incluidas claves
primarias, foráneas, índices e inserciones. Desactiva temporalmente las
comprobaciones de claves foráneas durante la restauración y las vuelve a activar
al terminar.

Para restaurarlo en otra base con el mismo nombre:

```powershell
Get-Content .\database\tupymegestion.sql | mysql -u root -p
```

Después de restaurar, configura `backend/.env` con el usuario y contraseña de
esa instalación y ejecuta `manage.py check`.

## Problemas comunes

### MySQL no conecta

Comprueba que el servicio MySQL esté iniciado y que `DB_NAME`, `DB_USER`,
`DB_PASSWORD`, `DB_HOST` y `DB_PORT` coincidan con `backend/.env`.

### Django responde 403

Comprueba que la URL del navegador esté incluida en
`DJANGO_CSRF_TRUSTED_ORIGINS`, reinicia Django y vuelve a solicitar `/api/auth/csrf/`.

### Mercado Pago responde 401 en el webhook

Comprueba que la URL pública llegue a Django, que el evento sea **Pagos**, que
la clave secreta pertenezca a la misma configuración de Webhooks y que Django
haya sido reiniciado después de cambiar el `.env`.

### La base demo no se duplica

El seed usa un identificador. Si ya existe el mismo dataset, informa que no lo
duplica. Para una demo completamente nueva usa `00_reset_database.sql` o un
`--seed` diferente.

### Mantenedores no permite entrar

Usa la cuenta `admin@demo-local-2026.tupyme.local`. Una cuenta PYME normal no
obtiene acceso global solo por tener una membresía de empresa.

### No aparece el botón Eliminar

Es normal que no aparezca en una cuenta recién creada. El seed entrega acceso
global, pero no activa la capacidad destructiva. Ejecuta el comando
`promote_platform_destructive_admin`, cierra sesión, vuelve a entrar y actualiza
la pantalla.

### Después de cerrar sesión aparece un 403 en `/api/auth/me/`

Es una respuesta esperada: el navegador está preguntando por la sesión después
de haberla cerrado. Al iniciar sesión nuevamente, `/api/auth/me/` debe responder
`200`.

## Estructura principal

```text
TuPymeGestiona/
├── backend/                         Django, DRF y reglas de negocio
├── frontend/                        Angular principal y mantenedores
├── database/
│   ├── 00_reset_database.sql        reinicio local destructivo
│   ├── 01_create_database.sql       creación no destructiva
│   ├── 02_poblar_demo.ps1           migraciones y seed
│   ├── 03_generar_tupymegestion_sql.ps1
│   └── tupymegestion.sql            snapshot generado desde MySQL
├── Cargar_Datos_Demo.cmd            atajo local para el seed
└── README.md
```

## Idea central

TuPymeGestiona busca que una PYME pueda ordenar su operación sin tener que
combinar varias herramientas desconectadas. El proyecto está pensado para
aprender, probar y discutir en equipo: cada integrante puede levantarlo en su
computador, recorrer los mismos datos demo y proponer cambios sobre una base
común.
