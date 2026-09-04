# RF24 — Evidencia de dos aplicaciones conectadas

## Aplicación 1
- Proyecto: `frontend`
- Source root: `frontend/src`
- Desarrollo: `npm start`
- Build: `npm run build`
- Bundle: `frontend/dist/frontend`

## Aplicación 2
- Proyecto: `maintainers`
- Source root: `frontend/projects/maintainers/src`
- Entrada: `frontend/projects/maintainers/src/main.ts`
- Desarrollo: `npm run start:maintainers`
- Puerto: `4300`
- Tests: `npm run test:maintainers`
- Build: `npm run build:maintainers`
- Bundle: `frontend/dist/maintainers`

## Conexión
Ambas aplicaciones consumen el mismo backend Django. Maintainers usa `/api/auth/*`,
`/api/organizations/context/`, `/api/administration/*`, `/api/catalog/*` y
`/api/organizations/warehouses/*`.

No existe tenant ni base de datos paralela. La autorización permanece en backend.

## Demostración manual
Con Django activo en `127.0.0.1:8000`, desde `frontend` ejecutar en dos terminales:

```bash
npm start
npm run start:maintainers
```

La evidencia automatizada de este checkpoint exige backend verde, 29 specs principales,
2 specs secundarios y build de ambos proyectos.
