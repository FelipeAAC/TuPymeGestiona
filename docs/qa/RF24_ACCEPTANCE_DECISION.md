# RF24 — decisión de aceptación pendiente

## Estado

`PARCIAL_TRAZABILIDAD`

La auditoría RF01-RF26 identificó que la evidencia actual concentra Administración y mantenedores dentro del mismo frontend Angular bajo `/app/administration`, mientras que la ERS/Acta utilizada por QA hace referencia a una aplicación secundaria dedicada y a “dos aplicaciones conectadas”.

## Decisión de este slice

Este paquete **no crea artificialmente una segunda aplicación** sin una confirmación de aceptación que justifique ese cambio arquitectónico. Hacerlo aumentaría el alcance, duplicaría autenticación/contexto organizacional y podría introducir una arquitectura que no sea exigida por la evaluación final.

Por lo tanto:

- RF05, RF06, RF16 y RF17 se corrigen con evidencia ejecutable.
- RF24 conserva `PARCIAL_TRAZABILIDAD`.
- Documentación v2 debe reconciliar explícitamente la frase “segunda aplicación”.
- Si la comisión exige dos ejecutables/frontend separados, debe abrirse un slice funcional específico antes del cierre académico.

Esta decisión evita declarar `CUMPLE` sin evidencia.
