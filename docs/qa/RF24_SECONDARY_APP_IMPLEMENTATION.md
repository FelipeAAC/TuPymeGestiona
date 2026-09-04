# RF24 — Aplicación secundaria de mantenedores

## Estado publicado
- HEAD: `8869bed986735485a8c61f9b89ee91e2e661a642`
- Commit: `feat(maintainers): add secondary administration application`
- Principal: proyecto `frontend`
- Secundaria: proyecto `maintainers`
- Backend: Django `/api/*`
- Base real: MySQL

## Separación ejecutable
Maintainers dispone de `projects/maintainers/src`, `main.ts`, `index.html`, proxy, tsconfig,
tests, `npm run start:maintainers`, puerto 4300, `npm run build:maintainers` y bundle
`dist/maintainers`.

## Integración
Consume autenticación, contexto organizacional, Administración, Catálogo, Proveedores y Bodegas.
La autorización y el aislamiento por empresa siguen en backend.

## Cobertura
Empresa/sucursales, usuarios, roles/permisos, categorías, marcas/productos, proveedores, bodegas,
métodos de pago, estados editables y parámetros no secretos.

La publicación base reportó backend 535/535, npm audit 0, 29 specs principales,
2 specs/6 tests secundarios y ambos builds aprobados.
