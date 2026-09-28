# TuPymeGestiona

TuPymeGestiona es una plataforma web multiempresa orientada a pequeñas y medianas empresas (PYMES) que combina **gestión operativa** y **experiencia de compra para clientes finales** dentro de un mismo ecosistema.

El objetivo del proyecto es que distintas PYMES puedan administrar su operación —productos, categorías, inventario, bodegas, clientes, pedidos, ventas, pagos, usuarios, roles, facturación electrónica, reportes y dashboard— mientras los clientes finales disponen de un Portal Cliente desde el cual pueden descubrir tiendas, consultar catálogos, comprar y revisar su historial.

La plataforma no busca ser un clon de un marketplace masivo. La idea central es ofrecer una solución accesible para varias PYMES, donde cada comercio mantiene su propio contexto, información y permisos, pero comparte una infraestructura común y una experiencia de usuario coherente.

Una decisión importante del diseño actual es **persona primero**: una persona crea una única cuenta y, con esa misma identidad, puede comprar en distintas tiendas, crear posteriormente su propia PYME, administrar una o varias empresas y cambiar entre modo cliente y modo gestión **sin cerrar sesión**.

---

## ¿Qué es TuPymeGestiona?

TuPymeGestiona cubre dos experiencias principales.

### Para una PYME

Una empresa puede administrar:

- empresa y sucursales;
- usuarios, membresías, roles y permisos;
- categorías, marcas, productos y variantes;
- proveedores;
- bodegas e inventario;
- movimientos y transferencias de stock;
- clientes;
- pedidos y sus estados;
- ventas derivadas de pedidos y ventas directas POS;
- pagos internos en efectivo, transferencia y canales externos configurados;
- facturación electrónica y RIDE;
- reportes PDF/XLS;
- indicadores de dashboard;
- parámetros generales no secretos;
- mantenedores desde una segunda aplicación Angular independiente.

### Para un cliente final

Una persona puede:

- crear una cuenta sin elegir tienda;
- iniciar sesión y entrar al Portal Cliente;
- explorar múltiples PYMES;
- consultar catálogo y detalle de productos;
- realizar pedidos;
- revisar historial y detalle de compras;
- iniciar pagos Mercado Pago cuando la integración esté activada;
- crear posteriormente una PYME utilizando la misma cuenta.

---

## Cómo levantar el proyecto localmente

### 1. Requisitos previos

Se recomienda disponer de:

- **Windows 10/11** para usar los ejecutables `.cmd` incluidos;
- **Python 3.13** o una versión compatible con Django 6.1;
- **MySQL** para la base de datos real/local del proyecto;
- **Node.js 22.22.3+, 24.15.0+** o una release posterior soportada por Angular 22;
- **npm 11.17.0**, declarado en `frontend/package.json` y activado explícitamente en CI;
- **Git**.
- **PowerShell 5.1+** (incluido en Windows) para los scripts de preparación y carga.

El backend usa las dependencias fijadas en:

```text
backend/requirements.txt
```

El frontend usa:

```text
frontend/package.json
frontend/package-lock.json
```

### 2. Clonar el repositorio

```cmd
git clone https://github.com/FelipeAAC/TuPymeGestiona.git
cd TuPymeGestiona
git checkout develop-v2
```

### 3. Configurar el backend

Desde la raíz:

```cmd
cd backend
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Crear `backend/.env`. Este archivo es local y no debe versionarse.

Ejemplo mínimo para MySQL:

```text
DJANGO_SECRET_KEY=una-clave-local-larga
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DB_ENGINE=mysql
DB_NAME=tupymegestiona
DB_USER=tu_usuario
DB_PASSWORD=tu_password
DB_HOST=127.0.0.1
DB_PORT=3306
```

Variables opcionales relevantes:

```text
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:4200,http://127.0.0.1:4200,http://localhost:4300,http://127.0.0.1:4300
DJANGO_SESSION_COOKIE_SECURE=false
DJANGO_CSRF_COOKIE_SECURE=false
DJANGO_SECURE_SSL_REDIRECT=false
DB_CONN_MAX_AGE=60
```

### Base nueva

Si estás creando una base vacía para desarrollo, primero puedes crearla con el
archivo SQL incluido:

```powershell
Get-Content .\database\01_create_database.sql | mysql -u root -p
```

El archivo crea `tupymegestiona` con `utf8mb4`. Si usarás otro nombre, cambia
el identificador del SQL y usa el mismo valor en `DB_NAME` dentro de
`backend/.env`. Después aplica las migraciones:

```cmd
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py migrate
```

### Base existente

Si ya tienes una base MySQL utilizada durante el desarrollo, **no apliques migraciones a ciegas**. Revisa primero el plan y realiza un backup:

```cmd
cd backend
.\.venv\Scripts\python.exe manage.py showmigrations
.\.venv\Scripts\python.exe manage.py migrate --plan
```

Si el plan muestra migraciones pendientes, aplícalas después del backup con
`manage.py migrate` y vuelve a revisar el estado de la aplicación.

### 4. Levantar Django

```cmd
cd backend
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Backend:

```text
http://127.0.0.1:8000
```

### 5. Instalar frontend

En otra terminal:

```cmd
cd frontend
npm ci
```

### 6. Levantar aplicación principal

```cmd
npm start
```

Disponible en:

```text
http://localhost:4200
```

Rutas útiles:

```text
/portal                         Portal Cliente
/login                          Login
/portal/account                 Cuenta e historial
/portal/seller-onboarding       Crear una PYME
/app/dashboard                  Dashboard de gestión
/app/products                   Productos
/app/inventory                  Inventario
/app/orders                     Pedidos
/app/sales                      Ventas de pedidos y caja POS
/app/reports                    Reportes
```

### 7. Levantar aplicación secundaria de mantenedores

En una tercera terminal:

```cmd
cd frontend
npm run start:maintainers
```

Disponible en:

```text
http://localhost:4300
```

La aplicación `maintainers` tiene entrada, `sourceRoot`, tests, servidor y bundle propios, pero comparte el mismo backend Django, sesión, permisos, contexto de empresa y MySQL.

---

## Uso básico

## Registro persona primero

El registro público solicita únicamente datos personales básicos:

```text
nombre
apellido
correo
contraseña
```

No obliga a seleccionar una tienda, dirección ni un tipo excluyente de usuario.

Flujo:

```text
User
  ↓
Portal Cliente
  ↓
explorar tiendas / comprar
```

Cuando esa persona compra por primera vez en una tienda, se crea la relación comercial correspondiente:

```text
User
  ↓
CustomerPortalAccount
  ↓
Customer de esa Company
```

Comprar en otra PYME crea otra relación comercial, pero conserva el mismo `User`.

## Registrar una venta POS

La ruta `/app/sales` conserva el flujo de ventas derivadas de pedidos y agrega
una caja para registrar ventas directas. El cliente es opcional: si no se
selecciona uno, el backend usa o crea el cliente interno **Consumidor final**
de la empresa. El POS exige una bodega, valida y descuenta stock dentro de una
transacción y permite pagar con:

```text
Efectivo
Transferencia
```

El precio y la disponibilidad se toman nuevamente desde el backend. Una venta
POS pagada puede anularse desde su detalle; la anulación repone el stock y deja
la trazabilidad del movimiento. Las ventas creadas desde pedidos entregados
continúan funcionando con su flujo anterior.

## Crear mi PYME

Desde la misma cuenta:

```text
/portal/seller-onboarding
```

se puede crear una empresa. El backend crea el contexto empresarial, membresía, rol administrador, permisos, configuración inicial y sucursal base.

Después se puede navegar:

```text
Portal Cliente ⇄ Gestión PYME
```

sin cerrar sesión.

En esta etapa de prototipo la PYME se habilita inmediatamente. Una versión productiva debería añadir verificación de identidad del representante, RUT, razón social, contacto y existencia comercial.

---

## Arquitectura actual

```text
                              MySQL
                                ▲
                                │
                       Django + Django REST
                         backend/manage.py
                         127.0.0.1:8000
                                │
                  ┌─────────────┴─────────────┐
                  │                           │
         Angular principal            Angular maintainers
         proyecto frontend            proyecto maintainers
         localhost:4200               localhost:4300
                  │
          ┌───────┴────────┐
          │                │
     Portal Cliente    Gestión PYME
     /portal           /app/*
```

## Backend

El backend vigente está en:

```text
backend/
```

El entrypoint correcto es:

```text
backend/manage.py
```

Django/DRF concentra:

- autenticación por sesión;
- autorización y RBAC;
- aislamiento multiempresa;
- reglas de negocio;
- transacciones;
- idempotencia;
- persistencia MySQL;
- integraciones externas.

## Frontend principal

Proyecto Angular:

```text
frontend
```

Source root:

```text
frontend/src
```

Build:

```text
frontend/dist/frontend
```

## Aplicación secundaria

Proyecto Angular:

```text
maintainers
```

Source root:

```text
frontend/projects/maintainers/src
```

Build:

```text
frontend/dist/maintainers
```

Esta separación proporciona la estructura técnica prevista para RF24. La aceptación completa requiere ejecutar las dos aplicaciones y comprobar sus mantenedores, permisos, flujos y relación con la documentación formal.

## Código legado eliminado

La implementación histórica ubicada en `panel/`, su SQLite y bytecode Python versionado fueron eliminados durante la limpieza del repositorio. Ya no forman parte de la arquitectura ni de los pasos de ejecución.

La documentación técnica dispersa también fue consolidada en este `README.md`.
Los únicos archivos operativos adicionales son los scripts versionados de
creación y carga de la base MySQL.

---

## Módulos implementados

Backend principal:

| Módulo | Responsabilidad |
|---|---|
| `accounts` | usuarios, login, sesión |
| `organizations` | empresas, sucursales, membresías, roles, permisos, bodegas |
| `catalog` | categorías, marcas, productos, variantes, proveedores |
| `inventory` | existencias, movimientos y transferencias |
| `customers` | clientes comerciales por empresa |
| `orders` | pedidos, items y transiciones de estado |
| `sales` | ventas de pedidos, ventas POS, abonos, pagos, stock y eventos |
| `portal` | Portal Cliente, cuenta, pedidos y onboarding |
| `electronic_tax` | DTE, folios, RIDE, intercambio y operación |
| `administration` | mantenedores y parámetros generales |
| `external_payments` | Mercado Pago Checkout Pro |
| `transactional_notifications` | outbox y envío transaccional |
| `reports` | reportes de ventas/inventario y exportaciones |
| `dashboard` | métricas, alertas y actividad reciente |

## Evolución reciente del proyecto

Los slices principales de `develop-v2` incluyen:

```text
ventas y pagos internos
facturación electrónica backend
adaptador SII
RIDE e intercambio
Angular DTE
operación/recuperación tributaria
administración/mantenedores
Portal Cliente
Mercado Pago Sandbox
notificaciones SMTP/outbox
reportes PDF/XLS
dashboard real
segunda aplicación maintainers
cierre de identidad/onboarding persona-primero
```

---

## Base de datos MySQL

MySQL es la base de datos del proyecto. La configuración y los scripts de
entrega están preparados para MySQL 8.x y usan `utf8mb4`; la creación inicial
usa una collation Unicode compatible con instalaciones MySQL habituales.

El `settings.py` actual usa MySQL por defecto y configura:

- `utf8mb4`;
- `STRICT_TRANS_TABLES`;
- conexiones persistentes configurables;
- health checks de conexión.

## Django y consistencia

El código de dominio aplica validaciones adicionales mediante `clean()`, restricciones de base, transacciones `transaction.atomic`, locks `select_for_update`, idempotencia y autorización servidor.

Los flujos críticos de pedido, inventario, venta y pago no dependen únicamente del frontend para mantener consistencia.

---

## Datos demo

Para poder explorar visualmente el sistema con información realista existe:

```cmd
Cargar_Datos_Demo.cmd
```

Para una base recién creada, el flujo reproducible recomendado desde PowerShell
es:

```powershell
.\database\02_poblar_demo.ps1
```

El script ejecuta `check`, aplica las migraciones pendientes y llama al
comando oficial `seed_demo_data`. También admite un dataset pequeño para una
presentación:

```powershell
.\database\02_poblar_demo.ps1 -Seed presentacion -Companies 1 -Products 12 -Customers 20 -Orders 12
```

La carga usa los servicios reales del dominio, por lo que las ventas POS
demo descuentan stock y quedan asociadas a pagos de efectivo y transferencia.

El cargador valida la configuración, aplica las migraciones pendientes y se
detiene ante cualquier error antes de insertar datos.

## Dataset predeterminado

```text
5 PYMES
3 sucursales por PYME
4 bodegas por PYME
48 productos por PYME
2 variantes por producto
6 categorías por PYME
8 marcas por PYME
10 proveedores por PYME
70 clientes por PYME
36 pedidos por PYME
6 pedidos del cliente demo por PYME, distribuidos en distintos estados
2 ventas POS por PYME (una con Consumidor final y efectivo, otra con cliente y transferencia)
3 usuarios de personal por PYME
ventas y pagos derivados
stock normal, crítico y agotado
pedidos en varios estados
ventas pagadas y parciales
fechas distribuidas en aproximadamente 45 días
```

Aproximadamente:

```text
240 productos
480 variantes
350 clientes
355 clientes contando el Consumidor final de cada PYME
180 pedidos
10 ventas POS
```

más empresas, sucursales, usuarios, roles, inventario, movimientos, ventas y pagos.

Los pedidos/ventas usan servicios reales del dominio en lugar de insertar estados arbitrarios.

## Credenciales demo por defecto

Con el seed predeterminado:

```text
Propietario: owner@demo-local-2026.tupyme.local
Cliente:     cliente@demo-local-2026.tupyme.local
Contraseña:  DemoLocal2026!
```

Son credenciales exclusivamente locales.

## Cambiar el seed

```cmd
Cargar_Datos_Demo.cmd --seed mi-prueba
```

También se pueden reducir/aumentar volúmenes:

```cmd
Cargar_Datos_Demo.cmd --seed prueba2 --companies 3 --products 30 --customers 50 --orders 25
```

El seed es determinista e idempotente para un mismo identificador: si detecta el dataset completo, no vuelve a duplicarlo.
Si necesitas cargar ejemplos POS en una base que ya tiene un seed anterior,
usa un identificador nuevo con `-Seed`.

El comando se bloquea con `DEBUG=False`; está pensado únicamente para una
instancia local o de presentación.

El dataset **no fabrica pagos Mercado Pago ni DTE SII** para evitar presentar integraciones externas falsas.
Las ventas POS demo sí son operaciones internas completas y reversibles.

---

## Optimización y limpieza aplicada

La revisión general del repositorio prioriza cambios conservadores y deja el
árbol final enfocado en el código ejecutable y sus archivos operativos.

Principales ajustes:

- eliminación completa de `panel/` legado;
- eliminación de SQLite y `.pyc` que estaban versionados en el legado;
- eliminación de documentación duplicada/dispersa;
- consolidación documental en este README;
- eliminación de imports Python sin uso;
- eliminación de scaffolding vacío de Django;
- `noUnusedLocals` y `noUnusedParameters` activos en TypeScript;
- eliminación de una inyección Angular no utilizada;
- `DJANGO_SECRET_KEY` explícita para CI;
- configuración MySQL endurecida;
- CSRF preparado para puertos 4200 y 4300;
- reducción de consultas N+1 del Portal Cliente;
- selección de bodega con stock en un número fijo de queries;
- disponibilidad de variantes agregada/prefetch en catálogo;
- prefetch de sucursales en listado de tiendas;
- carga demo determinista mediante servicios de dominio.

No se realizaron cambios invasivos en modelos o contratos públicos únicamente por estética.

---

## Verificación de instalación

Después de instalar dependencias o cambiar variables de entorno, valida la
configuración y genera ambos bundles de producción:

```cmd
cd backend
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run

cd ..\frontend
npm run typecheck
npm run build
npm run build:maintainers
```

Para una presentación, confirma manualmente el recorrido de registro/login,
cambio de empresa, catálogo, inventario, pedido, caja POS, reversa, reportes y
la aplicación de mantenedores. Mercado Pago, SMTP y SII necesitan sus propias
credenciales y ambientes autorizados.

---

## Estado actual

El sistema dispone actualmente de:

- backend funcional multiempresa;
- Portal Cliente;
- identidad persona-primero;
- alta de PYME desde cuenta existente;
- cambio cliente ↔ gestión sin logout;
- inventario y pedidos;
- ventas de pedidos y caja POS con pagos internos;
- facturación electrónica base, RIDE e integración SII en código;
- Mercado Pago Sandbox en código;
- outbox y SMTP en código;
- reportes PDF/XLS;
- dashboard real;
- aplicación secundaria de mantenedores;
- cargador de datos demo poblados, incluyendo ventas POS.

## Pendiente para cierre real/controlado

1. Realizar backup MySQL.
2. Confirmar el estado con `showmigrations` y `migrate --plan`.
3. Aplicar migraciones pendientes en un paso controlado.
4. Cargar datos demo para exploración visual.
5. Probar manualmente compra, venta POS y reversa antes de la presentación.
6. Ejecutar E2E manual completo.
7. Activar Mercado Pago Sandbox con secretos externos.
8. Activar SMTP real de forma controlada.
9. Activar/validar SII solamente con certificados y credenciales autorizadas.

---

## Operación de integraciones

## Mercado Pago

Configuración principal por entorno:

```text
MERCADO_PAGO_ENABLED
MERCADO_PAGO_ACCESS_TOKEN_ENV
MERCADO_PAGO_WEBHOOK_SECRET_ENV
MERCADO_PAGO_RETURN_BASE_URL
MERCADO_PAGO_WEBHOOK_URL
MERCADO_PAGO_USE_SANDBOX_INIT_POINT
MERCADO_PAGO_ACCEPT_LIVE_MODE
```

No guardar tokens en Git ni en parámetros generales de la PYME.

## Notificaciones transaccionales

Principio:

```text
evento de negocio → outbox persistente → procesador SMTP separado
```

Preflight:

```cmd
cd backend
.\.venv\Scripts\python.exe manage.py transactional_email_preflight
```

Procesar outbox:

```cmd
.\.venv\Scripts\python.exe manage.py process_transactional_notifications --limit 100
```

Recuperar envíos atascados:

```cmd
.\.venv\Scripts\python.exe manage.py transactional_email_recover_stale
```

Un envío `UNCERTAIN` no se reenvía ciegamente para evitar duplicados.

## Facturación electrónica / SII

Preflight:

```cmd
cd backend
.\.venv\Scripts\python.exe manage.py sii_preflight
```

Comprobación operacional:

```cmd
.\.venv\Scripts\python.exe manage.py electronic_tax_operational_check
```

Integridad:

```cmd
.\.venv\Scripts\python.exe manage.py electronic_tax_integrity_check --fail-on-problem
```

Procesamiento de consultas de estado en modo dry-run:

```cmd
.\.venv\Scripts\python.exe manage.py electronic_tax_process_status_checks
```

La ejecución remota requiere configuración SII real y autorización explícita.

---

## Política de errores API

Semántica general utilizada por el proyecto:

- **400**: entrada inválida o validación;
- **403**: usuario autenticado sin permiso/contexto requerido;
- **404**: recurso inexistente o no visible dentro del tenant autorizado;
- **409**: conflicto de estado, idempotencia o transición de negocio;
- **5xx**: fallo inesperado; nunca debe exponer secretos o stack traces al usuario final.

La autorización multiempresa se controla en backend, no únicamente ocultando botones en Angular.

---

## Seguridad

Nunca versionar:

- `backend/.env`;
- `DJANGO_SECRET_KEY` productiva;
- contraseña MySQL;
- access token/webhook secret de Mercado Pago;
- usuario/contraseña SMTP;
- contraseña de certificado SII;
- PFX/CAF privados;
- otros secretos productivos.

Para producción:

```text
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=<dominios reales>
DJANGO_SESSION_COOKIE_SECURE=true
DJANGO_CSRF_COOKIE_SECURE=true
DJANGO_SECURE_SSL_REDIRECT=true
```

---

## Comandos útiles

## Revisar estado Git

```cmd
git status
git log --oneline -10
```

## Ver migraciones

```cmd
cd backend
.\.venv\Scripts\python.exe manage.py showmigrations
```

## Crear la base MySQL

Ejecuta `database/01_create_database.sql` desde tu cliente MySQL y configura las
credenciales en `backend/.env`.

## Cargar datos demo

```cmd
Cargar_Datos_Demo.cmd
```

## Ejecutar backend

```cmd
cd backend
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

## Ejecutar Angular principal

```cmd
cd frontend
npm start
```

## Ejecutar mantenedores

```cmd
cd frontend
npm run start:maintainers
```

---

## Solución de problemas comunes

## `DJANGO_SECRET_KEY` no existe

Verifica que `backend/.env` exista y contenga:

```text
DJANGO_SECRET_KEY=...
```

## No conecta a MySQL

Verifica:

```text
DB_NAME
DB_USER
DB_PASSWORD
DB_HOST
DB_PORT
```

Luego ejecuta:

```cmd
cd backend
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py showmigrations
```

## Hay migraciones pendientes

No cargues datos demo todavía. Revisa:

```cmd
cd backend
.\.venv\Scripts\python.exe manage.py showmigrations
.\.venv\Scripts\python.exe manage.py migrate --plan
```

Haz backup antes de aplicar una migración sobre la base real.

## Advertencias `LF will be replaced by CRLF`

Son normales en Git sobre Windows mientras `git diff --check` no reporte un error real de whitespace.

## Puerto ocupado

Puertos esperados:

```text
8000 Django
4200 Angular principal
4300 Angular maintainers
```

---

## Estructura del repositorio

```text
TuPymeGestiona/
├── README.md
├── Cargar_Datos_Demo.cmd
├── database/
│   ├── 01_create_database.sql
│   └── 02_poblar_demo.ps1
├── backend/
├── frontend/
├── .gitignore
└── .gitattributes
```

La intención es mantener el repositorio centrado en código ejecutable, los
scripts de base necesarios y una única fuente de documentación humana: este
README.
