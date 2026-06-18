# TuPymeGestiona

## Descripción

Este proyecto es una aplicación Django pensada para gestionar procesos internos de una pyme. Incluye una interfaz web con funcionalidades de administración y datos guardados en SQLite para desarrollo.

## Requisitos previos

Para poder ejecutar la aplicación necesitas:

- Python 3.8 o superior
- pip (gestor de paquetes de Python)
- Git (opcional, necesario solo si quieres clonar el repositorio desde GitHub)
- Un editor de texto o IDE opcional, como Visual Studio Code

### ¿Qué más puede ser útil?

- Conocer comandos básicos de terminal (PowerShell, CMD o bash)
- No es obligatorio ser programador: con estos pasos cualquier persona puede arrancar la app localmente

## Antes de empezar

En este repositorio, el archivo `manage.py` se encuentra dentro de la carpeta `panel`. Por eso, siempre inicia los comandos desde esa carpeta.

Si ya tienes los archivos en tu equipo, solo abre la terminal en `TuPymeGestiona\panel`.

## Instalación y configuración

1. **Clonar el repositorio (opcional)**

Si aún no tienes el proyecto descargado, usa Git:

```
git clone https://github.com/<tu_usuario>/TuPymeGestiona.git
cd TuPymeGestiona\panel
```

Si ya tienes el proyecto en tu PC, abre la terminal directamente en `panel`.

2. **Crear el entorno virtual**

Crea un espacio aislado para las dependencias del proyecto:

```
py -3 -m venv .venv
```

Si tu equipo ya reconoce `python`:

```
python -m venv .venv
```

3. **Activar el entorno virtual**

En PowerShell:

```
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force
.\.venv\Scripts\Activate.ps1
```

En CMD:

```
.venv\Scripts\activate
```

Si prefieres no activar el entorno, puedes usar directamente el ejecutable de Python:

```
.\.venv\Scripts\python.exe manage.py migrate
```

4. **Instalar dependencias**

Si hay un archivo `requirements.txt`, ejecuta:

```
pip install -r requirements.txt
```

Si no existe, instala Django directamente:

```
pip install django
```

5. **Aplicar migraciones**

Esto prepara la base de datos SQLite y crea las tablas necesarias:

```
python manage.py migrate
```

6. **Crear un superusuario (opcional)**

Si quieres acceder al panel de administración de Django:

```
python manage.py createsuperuser
```

7. **Iniciar el servidor de desarrollo**

Arranca la aplicación localmente:

```
python manage.py runserver
```

Luego abre el navegador en:

```
http://127.0.0.1:8000/
```

## Comandos útiles

- Ejecutar tests:

```
python manage.py test
```

- Generar archivos estáticos (para producción):

```
python manage.py collectstatic
```

## Qué necesitas instalar en tu PC

- Python 3.8+ desde https://www.python.org/
- Git desde https://git-scm.com/ (solo si vas a clonar el repositorio)
- Un editor como Visual Studio Code o cualquier editor de texto

## Solución de problemas comunes

- Si ves `Python not found`, prueba con `py -3` o instala Python y marca “Add Python to PATH”.
- Si PowerShell bloquea la ejecución, ejecuta:

```
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force
```

- Si falta Django (`ModuleNotFoundError: No module named 'django'`), asegúrate de activar el entorno virtual e instala las dependencias:

```
pip install -r requirements.txt
```

- Si no tienes `requirements.txt`, instala Django y luego guarda las dependencias con:

```
pip freeze > requirements.txt
```

## Notas finales

- La base de datos usada en desarrollo es SQLite (`db.sqlite3` dentro de `panel/`). No hace falta configurar nada extra para empezar.
- Si quieres poner la app en producción, recuerda configurar `DEBUG=False`, `ALLOWED_HOSTS` y usar un servidor adecuado.