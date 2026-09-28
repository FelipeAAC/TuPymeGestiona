@echo off
setlocal
set "ROOT=%~dp0"
set "PYTHON=%ROOT%backend\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
  echo ERROR: no se encontro backend\.venv\Scripts\python.exe
  exit /b 1
)

echo ==^> Validar configuracion Django y aplicar migraciones
pushd "%ROOT%backend"
"%PYTHON%" manage.py check
if errorlevel 1 (
  popd
  echo.
  echo La validacion de Django termino con error.
  exit /b 1
)
"%PYTHON%" manage.py migrate --noinput
if errorlevel 1 (
  popd
  echo.
  echo Las migraciones terminaron con error.
  exit /b 1
)

echo.
echo ==^> Cargar dataset demo poblado
"%PYTHON%" manage.py seed_demo_data %*
set "EXIT_CODE=%ERRORLEVEL%"
popd

if not "%EXIT_CODE%"=="0" (
  echo.
  echo La carga demo termino con error.
  exit /b %EXIT_CODE%
)

echo.
echo OK: datos demo disponibles para explorar la aplicacion.
exit /b 0
