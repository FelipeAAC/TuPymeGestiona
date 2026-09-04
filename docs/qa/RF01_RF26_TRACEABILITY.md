# QA y trazabilidad RF01-RF26

**Checkpoint técnico auditado:** `develop-v2` en `33fa009027159ab8ada6baa26a826861e070a01a`.

Este documento no declara cumplimiento por intuición. La clasificación cruza la ERS académica, los casos de uso, la cobertura visual y la evidencia verificable del repositorio en el checkpoint indicado. El objetivo del slice es identificar con precisión qué está cerrado, qué solo está cerrado en código y qué conserva brechas funcionales, de QA o de trazabilidad documental.

## Fuentes de referencia

- `Informe ERS.docx`: RF01-RF26 y su relación con CU001-CU025 / R.1-R.26.
- `Documento Caso Uso Extendido.docx`: actores, precondiciones, flujo normal y alternativos de CU001-CU025.
- `Documento Mockups(1).docx`: cobertura visual esperada de Dashboard, autenticación, mantenedores, inventario, pedidos, ventas, reportes, administración y ayuda.
- `Acta de constitución.docx`: criterio de aprobación de 26 requisitos y demostración de dos aplicaciones conectadas, Mercado Pago y descarga de reportes.
- `docs/quality/API_PUBLIC_CONTRACTS.md` y `docs/quality/API_ERROR_POLICY.md`: inventario de contratos y política técnica del checkpoint.

## Leyenda

- **CUMPLE**: existen implementación y evidencia automatizada suficientes para el alcance del RF.
- **CUMPLE_EN_CODIGO**: el comportamiento está implementado y probado localmente, pero la integración externa real está reservada para la fase final controlada.
- **CUMPLE_CON_DECISION_SEGURIDAD**: cumple la decisión técnica vigente, aunque una redacción documental anterior debe actualizarse.
- **PARCIAL_FUNCIONAL**: falta una operación exigida por el RF en el producto demostrable.
- **PARCIAL_UI**: backend ofrece parte del contrato, pero la UI no expone todo el ciclo exigido.
- **PARCIAL_QA**: el flujo existe, pero falta evidencia automatizada específica de una parte relevante.
- **PARCIAL_TRAZABILIDAD**: existe funcionalidad, pero la arquitectura/evidencia actual no coincide de manera demostrable con la formulación académica.

## Matriz

| RF | ERS | CU | Requisito | API | Pantalla | Estado | Observación |
|---|---|---|---|---|---|---|---|
| RF01 | 3.2.1 | CU001 | Gestionar usuarios | /api/administration/users/ | /app/administration | CUMPLE | Administración V2 expone alta/actualización y estado de usuarios con alcance por empresa. |
| RF02 | 3.2.2 | CU002 | Gestionar roles y perfiles de acceso | /api/administration/roles/ | /app/administration | CUMPLE | Roles y permisos están integrados al contexto de empresa y a la autorización del shell. |
| RF03 | 3.2.3 | CU003 | Gestionar empresas o tiendas | /api/administration/companies/ | /app/administration | CUMPLE | Existe creación y actualización de empresa desde Administración. |
| RF04 | 3.2.4 | CU004 | Gestionar sucursales | /api/administration/branches/ | /app/administration | CUMPLE | Sucursales se administran dentro del alcance de empresa. |
| RF05 | 3.2.5 | CU005 | Gestionar categorías de productos | /api/catalog/categories/ | /app/categories | PARCIAL_FUNCIONAL | La ERS exige crear, consultar, actualizar y deshabilitar. En el checkpoint, API y UI de categorías exponen lista/creación, pero no existe endpoint de detalle PATCH ni flujo Angular de actualización/deshabilitación. |
| RF06 | 3.2.6 | CU006 | Gestionar productos | /api/catalog/products/; /api/catalog/products/<id>/ | /app/products | PARCIAL_UI | Backend soporta consulta y PATCH de producto, pero el servicio/pantalla Angular del checkpoint exponen lista/creación y no un flujo de edición/baja; tampoco existe spec dedicada de Products. |
| RF07 | 3.2.7 | CU007 | Gestionar proveedores | /api/catalog/suppliers/; /api/catalog/suppliers/<id>/ | /app/suppliers | CUMPLE | Listado, creación y actualización están cubiertos en UI y pruebas. |
| RF08 | 3.2.8 | CU008 | Gestionar bodegas | /api/organizations/warehouses/; /api/organizations/warehouses/<id>/ | /app/warehouses | CUMPLE | Bodegas se gestionan por empresa/sucursal con pruebas de CRUD operativo. |
| RF09 | 3.2.9 | CU009 | Gestionar métodos de pago | /api/administration/payment-methods/ | /app/administration | CUMPLE | Configuración y estado se administran desde el módulo de Administración. |
| RF10 | 3.2.10 | CU010 | Gestionar estados de pedidos | /api/administration/order-statuses/<id>/ | /app/administration | CUMPLE | Administración controla los estados configurables sin sustituir las transiciones operacionales del módulo Pedidos. |
| RF11 | 3.2.12 | CU012 | Gestionar clientes | /api/customers/; /api/customers/<id>/ | /app/customers | CUMPLE | Registro, consulta y actualización de clientes están cubiertos por API, pantalla y tests. |
| RF12 | 3.2.13 | CU013 | Gestionar inventario y existencias | /api/inventory/stocks/; /api/inventory/options/ | /app/inventory | CUMPLE | Stock por empresa/bodega y opciones operacionales están integrados. |
| RF13 | 3.2.14 | CU014 | Registrar movimientos de inventario | /api/inventory/movements/; /api/inventory/transfers/ | /app/inventory | CUMPLE | Entradas/salidas/ajustes y transferencias cuentan con trazabilidad y pruebas. |
| RF14 | 3.2.15-3.2.16 | CU015/CU016 | Registrar pedidos y gestionar su estado | /api/orders/; /api/orders/<id>/{confirm,prepare,deliver,cancel}/ | /app/orders; /portal | CUMPLE | Pedido, líneas y transiciones explícitas se prueban en aplicación principal y el Portal crea pedidos. |
| RF15 | 3.2.17 | CU017 | Registrar y consultar ventas | /api/sales/; /api/sales/<id>/payments/; /api/sales/<id>/cancel/ | /app/sales | CUMPLE | Venta, pago, cancelación, historial y control de idempotencia están cubiertos. |
| RF16 | 3.2.18-3.2.19 | CU018/CU019 | Consultar tiendas, catálogo y detalle de productos | /api/portal/stores/; /api/portal/stores/<company>/catalog/; /api/portal/stores/<company>/products/<id>/ | /portal | PARCIAL_QA | La implementación incluye tienda, catálogo y detalle; la suite Angular existente prueba explícitamente tiendas/catálogo, pero no tiene una prueba dedicada que evidencie el detalle de producto de CU019. |
| RF17 | 3.2.21 | CU021 | Consultar estado e historial de pedidos | /api/portal/account/; /api/portal/orders/; /api/portal/orders/<id>/ | /portal/account | PARCIAL_QA | El flujo y endpoints existen, pero falta evidencia Angular dedicada para la pantalla de cuenta/historial. |
| RF18 | 3.2.20 | CU020 | Integrar proceso de pago con servicio externo | /api/portal/payments/orders/<id>/mercado-pago/* | /portal; /portal/payment-result | CUMPLE_EN_CODIGO | Mercado Pago Sandbox está integrado en código con idempotencia, retorno/webhook y reconciliación. La prueba E2E contra el servicio externo real se mantiene para la fase final controlada. |
| RF19 | 3.2.24 | CU024 | Enviar notificaciones por correo electrónico | capacidad interna transactional_notifications (sin raíz pública dedicada) | sin pantalla obligatoria; eventos de pedidos/pagos | CUMPLE_EN_CODIGO | Notificaciones transaccionales, persistencia, idempotencia y reintentos están cerrados en código con backend local/fake durante pruebas. SMTP real queda reservado para integración final. |
| RF20 | 3.2.22 | CU022 | Generar reportes de ventas | /api/reports/sales/; /api/reports/sales/export/{pdf,xls}/ | /app/reports | CUMPLE | Filtros, resumen y exportación PDF/XLS se validaron en Reportes. |
| RF21 | 3.2.23 | CU023 | Generar reportes de inventario | /api/reports/inventory/; /api/reports/inventory/export/{pdf,xls}/ | /app/reports | CUMPLE | Filtros de inventario y exportación PDF/XLS están implementados y probados. |
| RF22 | 3.2.25 | CU025 | Autenticar usuarios | /api/auth/csrf/; /api/auth/login/; /api/auth/me/; /api/auth/logout/ | /login | CUMPLE | Autenticación y acceso protegido se integran mediante CSRF/sesión y rutas protegidas. |
| RF23 | 3.2.25 | CU025 | Gestionar sesión segura | /api/auth/me/; /api/auth/logout/ | /login; /app/* | CUMPLE | La sesión y el acceso a rutas protegidas se comprueban junto con el contexto de membresía. |
| RF24 | 3.2.26 | CU001-CU011 | Administrar mantenedores mediante aplicación secundaria | /api/administration/* y APIs de mantenedores | /app/administration + rutas de mantenedores dentro del mismo frontend Angular | PARCIAL_TRAZABILIDAD | La funcionalidad administrativa está integrada, pero la ERS exige una aplicación secundaria dedicada y el Acta exige demostrar dos aplicaciones conectadas. La evidencia actual muestra estos mantenedores dentro del mismo frontend/ruteo /app; debe reconciliarse o completarse antes de la aceptación. |
| RF25 | 3.2.11 | CU011 | Configurar parámetros generales del sistema | /api/administration/settings/ | /app/administration | CUMPLE_CON_DECISION_SEGURIDAD | Los parámetros no secretos están administrados. La ERS antigua menciona credenciales de APIs y SMTP, pero la decisión vigente exige mantener secretos fuera del dominio/repositorio; Documentación v2 debe alinear la redacción. |
| RF26 | 3.2.25 | CU025 | Restringir funcionalidades según rol/permisos | autorización transversal en endpoints + contexto de membresía | /app/*; /app/administration | CUMPLE | RBAC y aislamiento por empresa se aplican en backend y en navegación/acciones del frontend. |

## Hallazgos que deben conservarse

1. **RF05 Categorías — brecha funcional.** En el checkpoint existen listado y creación, pero no un contrato de detalle/actualización/deshabilitación equivalente al requerido por la ERS. No debe cerrarse como “cumple” solo porque la pantalla exista.
2. **RF06 Productos — brecha de UI.** El backend admite `PATCH` de producto, pero el servicio y la pantalla Angular actuales no exponen un flujo de edición/baja. La ausencia de `products.spec.ts` deja además una brecha de QA frontend.
3. **RF16 y RF17 — cobertura Angular incompleta.** Portal tiene contratos de detalle de producto y de cuenta/historial, pero las 26 specs del checkpoint no incluyen una prueba dedicada de detalle ni `portal-account.spec.ts`.
4. **RF18 y RF19 — cierre en código, no activación real.** Mercado Pago Sandbox y SMTP están preparados y probados sin dependencias externas durante la suite; credenciales y pruebas reales se reservan para integración controlada.
5. **RF24 — observación de aceptación.** La ERS exige una aplicación secundaria dedicada y el Acta habla de “dos aplicaciones conectadas”; la evidencia actual concentra Administración/mantenedores dentro del mismo frontend Angular. Documentación v2 debe resolver la contradicción y, si la comisión exige separación ejecutable, debe programarse una corrección funcional antes del cierre.
6. **RF25 — seguridad prevalece sobre redacción antigua.** El sistema administra parámetros no secretos. Credenciales de Mercado Pago/SMTP/SII permanecen fuera del repositorio y no deben trasladarse a un mantenedor solo para reproducir literalmente una redacción antigua de la ERS.

## Resultado del slice QA

Este slice **no modifica lógica funcional** para ocultar brechas. Publica una línea base auditable y reejecuta las puertas técnicas antes del commit. Las brechas detectadas deben alimentar el siguiente slice, **Documentación v2**, y cualquier corrección funcional que la reconciliación documental confirme como obligatoria.
