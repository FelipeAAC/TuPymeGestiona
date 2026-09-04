# Identidad y onboarding: persona primero

## Decisión

La identidad raíz de TuPymeGestiona es la persona (`User`), no la tienda y no un rol exclusivo
de "cliente" o "vendedor".

Una misma sesión puede representar simultáneamente:

- una persona que explora y compra en distintas PYMES;
- un cliente comercial de una o varias tiendas cuando efectivamente compra;
- un propietario/administrador de una o varias PYMES mediante `CompanyMembership`;
- un vendedor o colaborador de otras PYMES mediante roles y permisos.

## Registro

El registro público crea únicamente la identidad global:

`User -> sesión autenticada -> Portal Cliente`

No obliga a seleccionar tienda, dirección de despacho ni tipo de usuario.

Por compatibilidad, el backend sigue aceptando temporalmente el payload legado con `company`;
la interfaz nueva no lo utiliza.

## Relación con una tienda al comprar

`Customer` conserva su significado comercial dentro de una empresa. No representa la identidad
global de la persona.

Cuando un usuario realiza su primera compra en una tienda:

`User -> CustomerPortalAccount -> Customer -> Company`

La relación se materializa en ese momento usando la dirección del pedido. Comprar en una segunda
tienda crea una relación comercial separada, pero conserva el mismo `User`.

## Crear una PYME

Un usuario autenticado puede usar el endpoint de autoservicio:

`POST /api/administration/self-service/companies/`

La operación crea:

- `Company`;
- `CompanyMembership` ACTIVE para la persona;
- rol `Administrador`;
- asignación de permisos;
- configuración inicial;
- sucursal `CASA / Casa Matriz`.

La aplicación principal y el Portal Cliente siguen usando la misma sesión. Desde el portal se puede
entrar al panel de gestión y desde el panel volver al portal sin logout.

## Verificación de comercio

En esta etapa académica/prototipo la creación es inmediata.

Antes de una puesta en producción real se recomienda agregar un workflow separado:

`PENDIENTE_VERIFICACION -> VERIFICADA / RECHAZADA`

con validación de identidad del representante, RUT, razón social, datos de contacto y evidencia de
existencia comercial. Esa verificación no se simula en el prototipo para no presentar controles falsos.

## Seguridad

Crear una PYME no expone secretos ni entrega acceso a otras empresas. La nueva membresía solo da
permisos sobre la empresa recién creada; el aislamiento multiempresa y el RBAC siguen en backend.
