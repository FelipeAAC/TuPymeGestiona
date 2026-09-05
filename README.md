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
- ventas y pagos internos;
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
- **npm**;
- **Git**.

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

Si estás creando una base vacía para desarrollo:

```cmd
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py migrate
```

### Base existente

Si ya tienes la base MySQL utilizada durante el desarrollo, **no apliques migraciones a ciegas**. Desde la raíz del repositorio ejecuta primero:

```cmd
Revisar_MySQL.cmd
```

Este comando es de solo lectura. Revisa migraciones, versión/configuración MySQL, integridad multiempresa y anomalías de datos.

Existe una migración conocida que fue versionada pero que los módulos QA anteriores no aplicaron sobre la base real:

```text
backend/catalog/migrations/0009_category_status.py
```

Si `Revisar_MySQL.cmd` informa que continúa pendiente, debe aplicarse en un paso controlado y con backup previo.

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
/app/sales                      Ventas
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

Esta separación satisface RF24 mediante dos aplicaciones frontend ejecutables conectadas al mismo backend.

## Código legado eliminado

La implementación histórica ubicada en `panel/`, su SQLite y bytecode Python versionado fueron eliminados durante la limpieza del repositorio. Ya no forman parte de la arquitectura ni de los pasos de ejecución.

La documentación técnica dispersa también fue consolidada en este único `README.md` para mantener una fuente de verdad clara.

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
| `sales` | ventas, abonos, pagos y eventos |
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
calidad técnica
QA RF01-RF26
segunda aplicación maintainers
cierre RF24
identidad/onboarding persona-primero
QA de identidad/onboarding
```

---

## Base de datos MySQL

MySQL es la base de datos real del proyecto.

SQLite se mantiene únicamente como motor temporal para pruebas automatizadas cuando los scripts establecen explícitamente:

```text
DB_ENGINE=sqlite
```

El `settings.py` actual usa MySQL por defecto y configura:

- `utf8mb4`;
- `STRICT_TRANS_TABLES`;
- conexiones persistentes configurables;
- health checks de conexión.

## Auditoría read-only

Desde la raíz:

```cmd
Revisar_MySQL.cmd
```

El comando verifica sin modificar datos:

- motor MySQL real;
- versión del servidor;
- `sql_mode` global y de la sesión Django, incluyendo modo estricto;
- charset/collation;
- tablas fuera de InnoDB;
- migraciones pendientes;
- relaciones multiempresa inconsistentes;
- bodegas/sucursales cruzadas;
- productos/categorías/marcas cruzadas;
- stock de otra empresa;
- stock negativo;
- pedidos con sucursal/bodega/cliente incorrectos;
- items de pedido cruzados;
- ventas cruzadas;
- pagos superiores al total;
- `CustomerPortalAccount` inconsistente;
- SKU duplicados por empresa;
- códigos de clientes duplicados;
- RUT empresariales duplicados;
- volumen actual de datos.

No imprime la contraseña de MySQL ni otros secretos.

## Django y consistencia

El código de dominio aplica validaciones adicionales mediante `clean()`, restricciones de base, transacciones `transaction.atomic`, locks `select_for_update`, idempotencia y autorización servidor.

Los flujos críticos de pedido, inventario, venta y pago no dependen únicamente del frontend para mantener consistencia.

---

## Datos demo

Para poder explorar visualmente el sistema con información realista existe:

```cmd
Cargar_Datos_Demo.cmd
```

El ejecutable primero lanza `Revisar_MySQL.cmd`. Si la base no está sana o existen migraciones pendientes, **no carga datos**.

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
180 pedidos
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

El comando se bloquea con `DEBUG=False` salvo uso explícito de `--force-production`. No se recomienda usar datos demo en producción.

El dataset **no fabrica pagos Mercado Pago ni DTE SII** para evitar presentar integraciones externas falsas.

---

## Optimización y limpieza aplicada

La revisión general del repositorio prioriza cambios conservadores, sin reescribir módulos que ya tienen pruebas y comportamiento estable.

Principales ajustes:

- eliminación completa de `panel/` legado;
- eliminación de SQLite y `.pyc` que estaban versionados en el legado;
- eliminación de documentación duplicada/dispersa;
- consolidación documental en este README;
- eliminación de imports Python sin uso;
- eliminación de scaffolding vacío de Django;
- `noUnusedLocals` y `noUnusedParameters` activos en TypeScript;
- eliminación de una inyección Angular no utilizada;
- runner único de specs Angular en procesos aislados;
- CI validando también `maintainers`;
- `DJANGO_SECRET_KEY` explícita para CI;
- configuración MySQL endurecida;
- CSRF preparado para puertos 4200 y 4300;
- reducción de consultas N+1 del Portal Cliente;
- selección de bodega con stock en un número fijo de queries;
- disponibilidad de variantes agregada/prefetch en catálogo;
- prefetch de sucursales en listado de tiendas;
- nuevas pruebas de eficiencia de queries;
- herramientas de diagnóstico MySQL y datos demo.

No se realizaron cambios invasivos en modelos o contratos públicos únicamente por estética.

---

## Pruebas y calidad

## Baseline de este refactor

Después de incorporar las nuevas pruebas de rendimiento/tooling, el gate esperado es:

```text
Backend Django:                    547 tests
Angular principal:                 31 archivos spec
Angular maintainers:               2 archivos spec / 6 tests
npm audit high/critical:            0 vulnerabilidades
Build frontend:                     OK
Build maintainers:                  OK
RF01-RF26 parciales:                0
RF24:                               CUMPLE
```

El módulo de aplicación solo realiza commit/push si todos estos gates pasan.

## Backend

```cmd
cd backend
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test
```

## Frontend

```cmd
cd frontend
npm ci
npm audit --audit-level=high
npm run typecheck
npm run test:isolated
npm run test:maintainers
npm run build
npm run build:maintainers
```

`npm run test:isolated` descubre automáticamente los 31 specs de la aplicación principal y ejecuta cada archivo en un proceso independiente. Esto reduce los picos de memoria observados en Windows.

## Gate completo frontend

```cmd
npm run quality:frontend
```

## Verificadores internos

```cmd
backend\.venv\Scripts\python.exe scripts\qa\verify_repository_hygiene.py --repository .
backend\.venv\Scripts\python.exe scripts\qa\verify_identity_onboarding.py --repository .
backend\.venv\Scripts\python.exe scripts\qa\verify_rf_traceability.py --repository .
```

---

## Estado RF01-RF26

Clasificación de cierre actual:

```text
CUMPLE:                          23
CUMPLE_EN_CODIGO:                2
CUMPLE_CON_DECISION_SEGURIDAD:   1
PARCIALES:                       0
TOTAL:                          26
```

## RF18 — Mercado Pago

Estado:

```text
CUMPLE_EN_CODIGO
```

La integración está implementada y probada en código. El E2E contra servicio externo se reserva para activación controlada con credenciales Sandbox.

## RF19 — Notificaciones

Estado:

```text
CUMPLE_EN_CODIGO
```

Existe outbox transaccional, reintentos y procesamiento SMTP. La entrega SMTP real se activa posteriormente con credenciales de entorno.

## RF24 — segunda aplicación

Estado:

```text
CUMPLE
```

Existen dos proyectos Angular ejecutables:

```text
frontend
maintainers
```

ambos conectados al mismo Django/MySQL.

## RF25 — parámetros y secretos

Estado:

```text
CUMPLE_CON_DECISION_SEGURIDAD
```

Los parámetros generales no secretos pueden administrarse. Credenciales, tokens, certificados y contraseñas permanecen fuera del dominio administrativo y del repositorio.

---

## Estado actual

El sistema dispone actualmente de:

- backend funcional multiempresa;
- Portal Cliente;
- identidad persona-primero;
- alta de PYME desde cuenta existente;
- cambio cliente ↔ gestión sin logout;
- inventario y pedidos;
- ventas y pagos internos;
- facturación electrónica base, RIDE e integración SII en código;
- Mercado Pago Sandbox en código;
- outbox y SMTP en código;
- reportes PDF/XLS;
- dashboard real;
- aplicación secundaria de mantenedores;
- suite automatizada amplia;
- auditoría MySQL read-only;
- cargador de datos demo poblados.

## Pendiente para cierre real/controlado

1. Ejecutar `Revisar_MySQL.cmd` contra la instancia real local.
2. Confirmar si `catalog.0009_category_status` sigue pendiente.
3. Realizar backup MySQL.
4. Aplicar la migración pendiente en un paso controlado si corresponde.
5. Ejecutar nuevamente `Revisar_MySQL.cmd`.
6. Cargar datos demo para exploración visual.
7. Ejecutar E2E manual completo.
8. Activar Mercado Pago Sandbox con secretos externos.
9. Activar SMTP real de forma controlada.
10. Activar/validar SII solamente con certificados y credenciales autorizadas.

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

## Revisar MySQL

```cmd
Revisar_MySQL.cmd
```

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
Revisar_MySQL.cmd
```

## Hay migraciones pendientes

No cargues datos demo todavía. Revisa:

```cmd
cd backend
.\.venv\Scripts\python.exe manage.py showmigrations
.\.venv\Scripts\python.exe manage.py migrate --plan
```

Haz backup antes de aplicar una migración sobre la base real.

## Angular consume demasiada memoria durante tests

Usa:

```cmd
npm run test:isolated
```

No ejecutes necesariamente todos los specs en un único proceso.

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
├── Revisar_MySQL.cmd
├── Cargar_Datos_Demo.cmd
├── backend/
├── frontend/
├── scripts/
├── .github/
├── .gitignore
└── .gitattributes
```

La intención es mantener el repositorio centrado en código ejecutable, pruebas, tooling y una única fuente de documentación humana: este README.
