# RF24 — Aplicación secundaria de mantenedores

## Base

- Rama: `develop-v2`
- HEAD de partida: `a2c81487c218c817e9446e05725afffa86912eb7`
- Aplicación principal: proyecto Angular `frontend`
- Aplicación secundaria: proyecto Angular `maintainers`
- Backend compartido: Django REST bajo `/api/*`
- Base real: MySQL
- SQLite: solo temporal durante pruebas backend

## Separación ejecutable

`maintainers` es un proyecto Angular independiente dentro del workspace existente. Tiene:

- `sourceRoot` propio: `projects/maintainers/src`
- `main.ts` propio
- `index.html` propio
- bundle de producción propio
- servidor de desarrollo propio, puerto `4300`
- pruebas unitarias propias
- proxy propio a Django

Comandos:

```bash
npm run start:maintainers
npm run test:maintainers
npm run build:maintainers
```

La aplicación principal queda explícita como proyecto `frontend` en sus scripts para que
la incorporación de un segundo proyecto no cambie los gates existentes.

## Integración

La secundaria consume los contratos existentes de autenticación, contexto de empresa,
Administración, Catálogo, Proveedores y Bodegas. No replica permisos en frontend:
la autorización y el aislamiento por empresa continúan siendo responsabilidad del backend.

## Mantenedores incluidos

1. Empresa/tienda.
2. Sucursales.
3. Usuarios.
4. Roles y permisos.
5. Categorías.
6. Marcas y productos.
7. Proveedores.
8. Bodegas.
9. Métodos de pago.
10. Estados de pedido editables.
11. Parámetros generales no secretos.

Los estados estructurales `is_system` se mantienen protegidos. Tokens, passwords,
CAF, PFX y secretos equivalentes no se muestran ni se almacenan en esta aplicación.

## Cierre de RF24

Este slice implementa la segunda aplicación, pero NO modifica todavía la matriz RF01–RF26.
RF24 solo debe pasar a `CUMPLE` después de que las pruebas, ambos builds, el backend completo,
el commit/push y un slice de revalidación de dos aplicaciones queden aprobados.
