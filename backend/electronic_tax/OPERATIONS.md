# Operacion de Facturacion Electronica

## Frontera de este slice

Este bloque agrega observabilidad, alertas, consultas de estado encoladas, verificacion de integridad y herramientas para contrastar respaldos. No activa CAF, certificados, correo ni trafico SII real. La activacion y certificacion oficial se realiza en un cierre separado.

MySQL es la base de datos real del proyecto. SQLite puede usarse exclusivamente como base efimera de pruebas automatizadas; no debe persistir en `.env`, `settings.py` ni en un despliegue.

## Rutinas operativas

- `python manage.py electronic_tax_operational_check`: recalcula alertas sin red. Puede ejecutarse periodicamente.
- `python manage.py electronic_tax_process_status_checks`: dry-run; informa consultas vencidas sin red.
- `python manage.py electronic_tax_process_status_checks --execute`: ejecuta consultas SII solo cuando el adaptador fue activado explicitamente y los activos reales estan configurados.
- `python manage.py electronic_tax_integrity_check --fail-on-problem`: comprueba relaciones folio/DTE y genera un digest sin material sensible.
- `python manage.py electronic_tax_backup_manifest --output <ruta.json>`: genera un manifiesto para contrastar un respaldo MySQL externo. No reemplaza `mysqldump`, snapshots del proveedor ni la restauracion probada.

## Alertas

La exploracion operativa cubre al menos:

- folios bajos o agotados por empresa y tipo DTE;
- CAF con `valid_to` vencido cuando ese dato existe;
- certificado no configurado, invalido o proximo a vencer cuando el adaptador real esta habilitado;
- DTE `SUBMITTED`, `PROCESSING` o `SEND_UNCERTAIN` sin resolucion durante el umbral configurado;
- intercambio al receptor en `SEND_UNCERTAIN`.

Un `SEND_UNCERTAIN` del SII nunca provoca reenvio ciego. Solo se encola una consulta de estado. Un envio de correo incierto tampoco se reenvia automaticamente, porque no existe una confirmacion remota segura que descarte duplicados.

## Cola de consultas

Las tareas `ElectronicTaxStatusCheckTask` son persistentes, conservan empresa, sucursal, DTE y actor, aplican backoff y tienen un maximo de intentos. El procesador es dry-run por defecto. Para habilitar ejecucion remota debe usarse explicitamente `--execute` y `SII_ADAPTER_ENABLED=true`.

## Respaldos y retencion

La aplicacion no intenta implementar un backup de MySQL dentro del proceso web. El respaldo debe realizarse en infraestructura, cifrado, con acceso restringido y con pruebas periodicas de restauracion. El manifiesto entregado por este modulo sirve para comparar conteos y digest de integridad antes/despues de una restauracion sin exponer secretos.

La retencion documental debe respetar la politica tributaria definida para el proyecto. Los DTE emitidos, sus eventos y evidencia fiscal no se eliminan mediante este modulo.

## Recuperacion

Ante una restauracion:

1. restaurar MySQL en un entorno aislado;
2. no habilitar trafico SII ni correo durante la prueba;
3. ejecutar migraciones y `manage.py check`;
4. ejecutar `electronic_tax_integrity_check --fail-on-problem`;
5. comparar el digest/manifiesto con el generado antes del respaldo;
6. validar folios, DTE en estados no terminales y tareas pendientes;
7. recien despues habilitar integraciones reales de forma controlada.
