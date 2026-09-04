# QA y trazabilidad RF01-RF26

**Checkpoint de entrada de Revalidación RF24:** `develop-v2` en `8869bed986735485a8c61f9b89ee91e2e661a642`.

RF24 deja de depender de una interpretación documental: existe un segundo proyecto Angular
ejecutable, `maintainers`, con entrada, sourceRoot, servidor, tests y bundle propios,
conectado al mismo backend Django.

## Matriz

| RF | ERS | CU | Requisito | Pantalla / aplicación | Estado | Observación |
|---|---|---|---|---|---|---|
| RF01 | 3.2.1 | CU001 | Gestionar usuarios | maintainers: Usuarios | **CUMPLE** | Usuarios administrables por empresa desde la segunda aplicación. |
| RF02 | 3.2.2 | CU002 | Gestionar roles y perfiles de acceso | maintainers: Roles y permisos | **CUMPLE** | Roles/permisos expuestos en maintainers y autorizados por backend. |
| RF03 | 3.2.3 | CU003 | Gestionar empresas o tiendas | maintainers: Empresa y sucursales | **CUMPLE** | Empresa creada/actualizada mediante el backend compartido. |
| RF04 | 3.2.4 | CU004 | Gestionar sucursales | maintainers: Empresa y sucursales | **CUMPLE** | Sucursales administrables en alcance de empresa. |
| RF05 | 3.2.5 | CU005 | Gestionar categorías de productos | /app/categories; maintainers: Catálogo | **CUMPLE** | ACTIVE/INACTIVE, listado de administración y PATCH con evidencia en ambos frontends. |
| RF06 | 3.2.6 | CU006 | Gestionar productos | /app/products; maintainers: Catálogo | **CUMPLE** | Actualización y baja lógica expuestas en principal y secundaria. |
| RF07 | 3.2.7 | CU007 | Gestionar proveedores | /app/suppliers; maintainers: Proveedores | **CUMPLE** | Proveedor administrable desde la secundaria y cubierto en principal. |
| RF08 | 3.2.8 | CU008 | Gestionar bodegas | /app/warehouses; maintainers: Bodegas | **CUMPLE** | Bodegas conectadas al mismo contexto organizacional. |
| RF09 | 3.2.9 | CU009 | Gestionar métodos de pago | maintainers: Pagos y estados | **CUMPLE** | Métodos de pago no secretos administrables en la secundaria. |
| RF10 | 3.2.10 | CU010 | Gestionar estados de pedidos | maintainers: Pagos y estados | **CUMPLE** | Estados configurables disponibles; is_system permanece protegido. |
| RF11 | 3.2.12 | CU012 | Gestionar clientes | /app/customers | **CUMPLE** | CRUD operativo de clientes cubierto. |
| RF12 | 3.2.13 | CU013 | Gestionar inventario y existencias | /app/inventory | **CUMPLE** | Stock por empresa/bodega integrado. |
| RF13 | 3.2.14 | CU014 | Registrar movimientos de inventario | /app/inventory | **CUMPLE** | Movimientos y transferencias con trazabilidad. |
| RF14 | 3.2.15-3.2.16 | CU015/CU016 | Registrar pedidos y gestionar su estado | /app/orders; /portal | **CUMPLE** | Pedido y transiciones explícitas probadas. |
| RF15 | 3.2.17 | CU017 | Registrar y consultar ventas | /app/sales | **CUMPLE** | Venta, pagos, cancelación e idempotencia cubiertos. |
| RF16 | 3.2.18-3.2.19 | CU018/CU019 | Consultar tiendas, catálogo y detalle de productos | /portal | **CUMPLE** | Portal cubre tienda, catálogo y detalle dedicado. |
| RF17 | 3.2.21 | CU021 | Consultar estado e historial de pedidos | /portal/account | **CUMPLE** | Historial y detalle de pedido con evidencia Angular. |
| RF18 | 3.2.20 | CU020 | Integrar proceso de pago con servicio externo | /portal; /portal/payment-result | **CUMPLE_EN_CODIGO** | Mercado Pago integrado; E2E externo reservado para integración final. |
| RF19 | 3.2.24 | CU024 | Enviar notificaciones por correo electrónico | eventos de pedidos/pagos | **CUMPLE_EN_CODIGO** | SMTP real reservado para integración final. |
| RF20 | 3.2.22 | CU022 | Generar reportes de ventas | /app/reports | **CUMPLE** | Reportes de ventas y exportaciones probados. |
| RF21 | 3.2.23 | CU023 | Generar reportes de inventario | /app/reports | **CUMPLE** | Reportes de inventario y exportaciones probados. |
| RF22 | 3.2.25 | CU025 | Autenticar usuarios | /login; login de maintainers | **CUMPLE** | Ambos frontends autentican contra la misma sesión Django. |
| RF23 | 3.2.25 | CU025 | Gestionar sesión segura | /app/*; maintainers | **CUMPLE** | Sesión y contexto de membresía compartidos por backend. |
| RF24 | 3.2.26 | CU001-CU011 | Administrar mantenedores mediante aplicación secundaria | proyecto Angular maintainers: projects/maintainers/src; npm run start:maintainers; puerto 4300 | **CUMPLE** | Segunda aplicación ejecutable con entrada, sourceRoot, tests, serve y bundle propios, conectada al mismo backend. |
| RF25 | 3.2.11 | CU011 | Configurar parámetros generales del sistema | maintainers: Parámetros | **CUMPLE_CON_DECISION_SEGURIDAD** | Parámetros no secretos administrables; credenciales y secretos permanecen fuera del dominio/repositorio. |
| RF26 | 3.2.25 | CU025 | Restringir funcionalidades según rol/permisos | /app/*; maintainers | **CUMPLE** | RBAC y aislamiento por empresa se mantienen en backend para ambos frontends. |

## Resultado esperado

- CUMPLE: **23**
- CUMPLE_EN_CODIGO: **2**
- CUMPLE_CON_DECISION_SEGURIDAD: **1**
- Parciales: **0**
- Total: **26**

RF18/RF19 conservan activación externa para integración final y RF25 conserva la decisión de
seguridad sobre secretos. El siguiente bloque recomendado es **Documentación v2**.
