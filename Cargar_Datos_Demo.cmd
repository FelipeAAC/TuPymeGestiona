@echo off
setlocal
set "ROOT=%~dp0"
set "PYTHON=%ROOT%backend\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
  echo ERROR: no se encontro backend\.venv\Scripts\python.exe
  exit /b 1
)

echo ==^> Verificar MySQL antes de cargar datos demo
call "%ROOT%Revisar_MySQL.cmd"
if errorlevel 1 (
  echo.
  echo No se cargaran datos demo hasta que Revisar_MySQL.cmd quede verde.
  exit /b 1
)

echo.
echo ==^> Cargar dataset demo poblado
pushd "%ROOT%backend"
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
