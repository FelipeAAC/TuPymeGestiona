# QA — Flujo de identidad y onboarding

## Checkpoint

- Rama: `develop-v2`
- Base: `a9291a2960d463e73188897a41efcda0cb34cb55`
- Commit funcional previo: `feat(identity): add user-first onboarding and seller mode`

## Objetivo

Probar el recorrido funcional que define la identidad de TuPymeGestiona:

`persona -> portal -> compra -> relación cliente/tienda -> crear PYME -> gestión -> volver al portal`

sin crear identidades duplicadas ni obligar a elegir tienda durante el registro.

## Evidencia requerida

1. El registro público crea un `User` y devuelve `account = null`.
2. El login normal redirige por defecto a `/portal`.
3. `/portal/seller-onboarding` está protegido por sesión.
4. La primera compra crea `Customer + CustomerPortalAccount` para esa tienda.
5. Dos compras en dos tiendas generan dos relaciones comerciales, pero conservan el mismo `User`.
6. Una segunda compra en la misma tienda reutiliza la relación existente.
7. El mismo usuario puede crear una PYME mediante `/api/administration/self-service/companies/`.
8. La PYME aparece en `/api/organizations/context/`.
9. Convertirse en propietario no elimina ni altera el historial de compras.
10. El panel de gestión conserva un enlace de retorno al Portal Cliente sin logout.
11. RF24 sigue verde y la aplicación secundaria sigue compilando/probándose.

## Gates de este slice

- Django system check.
- `makemigrations --check --dry-run`.
- QA dirigido de identidad.
- Suite backend completa.
- `npm ci`.
- `npm audit --audit-level=high`.
- Specs dirigidos de registro, cuenta, onboarding, login, rutas y shell.
- 31 specs principales en procesos independientes.
- Tests de `maintainers`.
- Build de `frontend`.
- Build de `maintainers`.
- Verificador específico de identidad.
- Verificador RF01-RF26.

## Límites

Este QA no activa Mercado Pago real, SMTP real ni SII real. Tampoco aplica migraciones sobre
MySQL. La verificación real de existencia comercial de una PYME continúa como mejora productiva
posterior; el prototipo permite alta inmediata.
