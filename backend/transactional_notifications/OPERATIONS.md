# Notificaciones transaccionales

## Principios
- El evento de negocio solo crea un registro de outbox; no abre conexiones SMTP dentro de la transacción.
- El envío real se realiza con `python manage.py process_transactional_notifications`.
- Los reintentos usan backoff y un máximo configurable.
- Un proceso interrumpido después de iniciar el envío queda `SENDING`; `transactional_email_recover_stale` lo mueve a `UNCERTAIN` y **no lo reenvía automáticamente** para evitar duplicados.
- Las credenciales SMTP se resuelven desde variables de entorno cuyos nombres se configuran en settings; nunca se almacenan en la base ni en Git.

## Operación recomendada
1. Ejecutar `python manage.py transactional_email_preflight`.
2. Programar `process_transactional_notifications --limit 100` cada 1-5 minutos.
3. Programar `transactional_email_recover_stale` cada 10-15 minutos.
4. Revisar registros `FAILED` y `UNCERTAIN` antes de cualquier reenvío manual.

## Configuración
- `TRANSACTIONAL_EMAIL_ENABLED`
- `TRANSACTIONAL_EMAIL_BACKEND`
- `TRANSACTIONAL_EMAIL_HOST`
- `TRANSACTIONAL_EMAIL_PORT`
- `TRANSACTIONAL_EMAIL_USE_TLS`
- `TRANSACTIONAL_EMAIL_USE_SSL`
- `TRANSACTIONAL_EMAIL_REQUIRE_AUTH`
- `TRANSACTIONAL_EMAIL_USERNAME_ENV`
- `TRANSACTIONAL_EMAIL_PASSWORD_ENV`
- `TRANSACTIONAL_EMAIL_FROM`

Durante pruebas automatizadas debe mantenerse `TRANSACTIONAL_EMAIL_ENABLED=false` y usarse un sender fake o backend local.
