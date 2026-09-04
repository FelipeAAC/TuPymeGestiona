# RF24 — decisión cerrada por evidencia ejecutable

## Estado
`CUMPLE`

La brecha anterior existía porque mantenedores estaban dentro del mismo frontend `/app`.
El slice publicado en `8869bed986735485a8c61f9b89ee91e2e661a642` creó `maintainers` como segundo proyecto Angular ejecutable.

La separación incluye sourceRoot propio, `main.ts`, `index.html`, puerto 4300, tests y bundle propios.
Ambas aplicaciones comparten Django, sesión, contexto organizacional y MySQL. No se duplican permisos
ni base de datos y los secretos siguen fuera de los mantenedores.

RF24 puede declararse `CUMPLE` únicamente si esta revalidación completa sus gates y se publica.
