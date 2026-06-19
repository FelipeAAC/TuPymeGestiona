# TuPymeGestiona

## Descripción

Este proyecto es una aplicación Django diseñada para gestionar los procesos internos de una pyme. Incluye una interfaz web funcional con módulos de administración y utiliza una base de datos SQLite optimizada para el entorno de desarrollo local.

## Requisitos Previos

* **Python:** Versión 3.8 o superior.
* **pip:** El gestor de paquetes por defecto de Python.
* **Git (Opcional):** Necesario únicamente si deseas clonar el repositorio de forma directa.
* **IDE/Editor:** Se recomienda el uso de Visual Studio Code o cualquier editor de texto técnico.

### Herramientas y Conocimientos Útiles
* Manejo básico de comandos de terminal (PowerShell, CMD o Bash).
* *Nota:* No es obligatorio ser desarrollador avanzado; siguiendo esta guía cualquier usuario puede inicializar la aplicación localmente.

---

## Antes de Empezar

> ⚠️ **Información Importante:** En este repositorio, el archivo estructural `manage.py` se encuentra alojado dentro del directorio `panel`. Por lo tanto, todos los comandos de Django deben ejecutarse siempre posicionándose dentro de dicha carpeta.

Si ya cuentas con los archivos en tu equipo, simplemente abre tu terminal en la ruta: `TuPymeGestiona\panel`.

---

## Instalación y Configuración

Sigue este paso a paso para desplegar el entorno de desarrollo en tu máquina local:

1.  **Clonar el Repositorio (Opcional):**
    Si aún no descargas el proyecto, ejecuta en tu terminal:
    ```bash
    git clone [https://github.com/](https://github.com/)<tu_usuario>/TuPymeGestiona.git
    cd TuPymeGestiona\panel
    ```
    Si ya posees los archivos en tu PC, abre la terminal directamente en la carpeta `panel`.

2.  **Crear el Entorno Virtual:**
    Construye un espacio aislado para gestionar las dependencias del sistema de manera limpia:
    ```bash
    py -3 -m venv .venv
    ```
    Si tu sistema operativo reconoce el comando estándar de Python de forma directa, utiliza:
    ```bash
    python -m venv .venv
    ```

3.  **Activar el Entorno Virtual:**
    Dependiendo de la terminal que utilices, ejecuta el comando correspondiente:
    * **En Windows (PowerShell):**
        ```bash
        Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force
        .\.venv\Scripts\Activate.ps1
        ```
    * **En Windows (CMD):**
        ```bash
        .venv\Scripts\activate
        ```
    * *Alternativa sin activación:* Si prefieres prescindir de la activación del entorno, puedes invocar directamente el binario ejecutable para correr las migraciones:
        ```bash
        .\.venv\Scripts\python.exe manage.py migrate
        ```

4.  **Instalar Dependencias del Proyecto:**
    Si el repositorio cuenta con el archivo de requerimientos, ejecútalo mediante:
    ```bash
    pip install -r requirements.txt
    ```
    En caso de que no exista el archivo en el directorio, instala el framework base directamente:
    ```bash
    pip install django
    ```

5.  **Aplicar Migraciones de la Base de Datos:**
    Este comando prepara el motor SQLite local y construye de manera automática todas las tablas e índices necesarios para la aplicación:
    ```bash
    python manage.py migrate
    ```

6.  **Crear un Superusuario (Opcional):**
    Si requieres acceder al panel de administración nativo de Django para gestionar los registros, genera tus credenciales ejecutando:
    ```bash
    python manage.py createsuperuser
    ```

7.  **Iniciar el Servidor de Desarrollo:**
    Para levantar la aplicación de forma local, utiliza el servidor embebido:
    ```bash
    python manage.py runserver
    ```
    Una vez inicializado, abre tu navegador web e ingresa a la siguiente dirección URL:
    ```text
    [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
    ```

---

## Ejecución de Comandos Útiles

* **Correr Pruebas Unitarias:**
    ```bash
    python manage.py test
    ```
* **Recopilar Archivos Estáticos:** (Esencial antes de preparar el proyecto para entornos de producción)
    ```bash
    python manage.py collectstatic
    ```

---

## Recursos de Instalación Externa

Si necesitas configurar las herramientas base en tu computadora, puedes obtenerlas desde sus sitios oficiales:
* [Descargar Python 3.8+](https://www.python.org/)
* [Descargar Git SCM](https://git-scm.com/)
* [Descargar Visual Studio Code](https://code.visualstudio.com/)

---

## Solución de Problemas Comunes (F.A.Q.)

* **Error: `Python not found`**
    * *Solución:* Intenta ejecutar los comandos utilizando el prefijo `py -3` en lugar de `python`, o reinstala el software asegurándote de marcar la casilla **“Add Python to PATH”** en el instalador oficial.
* **PowerShell bloquea la ejecución de scripts:**
    * *Solución:* Abre la consola de comandos y otorga permisos de ejecución temporales para el proceso actual mediante:
        ```bash
        Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force
        ```
* **Error de importación (`ModuleNotFoundError: No module named 'django'`):**
    * *Solución:* Este fallo ocurre si no se ha inicializado el entorno de aislamiento. Asegúrate de activar correctamente el entorno virtual `.venv` antes de intentar instalar las dependencias con `pip install -r requirements.txt`.
* **No encuentro el archivo `requirements.txt` en el repositorio:**
    * *Solución:* Instala Django manualmente y, una vez finalizado el proceso, puedes exportar el listado de paquetes instalados para dejar el archivo listo usando:
        ```bash
        pip freeze > requirements.txt
        ```

---

## Notas Finales y Despliegue

* **Persistencia en Desarrollo:** El proyecto está preconfigurado para interactuar con un archivo de base de datos local SQLite (`db.sqlite3`), ubicado dentro de la carpeta `panel/`. No se requiere realizar configuraciones ni instalaciones de motores de bases de datos adicionales para operar el PMV.
* **Entornos de Producción:** Antes de empaquetar o subir esta aplicación a un servidor web definitivo, es mandatorio modificar las variables de seguridad en el archivo `settings.py`, estableciendo `DEBUG = False`, definiendo los dominios permitidos en `ALLOWED_HOSTS` y reemplazando el motor SQLite por una base de datos de nivel corporativo (como PostgreSQL o MySQL).
