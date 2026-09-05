@echo off
setlocal
set "ROOT=%~dp0"
set "PYTHON=%ROOT%backend\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
  echo ERROR: no se encontro backend\.venv\Scripts\python.exe
  echo Crea el entorno virtual e instala backend\requirements.txt antes de continuar.
  exit /b 1
)

pushd "%ROOT%backend"
"%PYTHON%" manage.py diagnose_mysql --strict %*
set "EXIT_CODE=%ERRORLEVEL%"
popd

if not "%EXIT_CODE%"=="0" (
  echo.
  echo La auditoria MySQL encontro un problema. No se modifico la base de datos.
  exit /b %EXIT_CODE%
)

echo.
echo OK: MySQL e integridad critica revisados sin modificaciones.
exit /b 0
