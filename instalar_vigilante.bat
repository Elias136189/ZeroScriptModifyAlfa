@echo off
setlocal EnableDelayedExpansion

rem ============================================================
rem Instala el vigilante de cambios en el ARRANQUE de Windows.
rem - Usa la carpeta Inicio del usuario (no requiere admin).
rem - Se ejecuta al iniciar sesion, sin ventana (pythonw.exe).
rem - Logs en: <proyecto>\logs\registro_cambios\cambios_YYYY-WWW.log (semanal)
rem
rem Nota: la Tarea Programada (schtasks) esta bloqueada por politica
rem en este equipo; por eso se usa la carpeta Inicio.
rem ============================================================

set "PROJECT_DIR=%~dp0"
set "SCRIPT=%PROJECT_DIR%vigilante_cambios.py"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "VBS=%STARTUP_DIR%\ZeroScript_Vigilante_Cambios.vbs"
set "PYTHON_EXE="
set "PYTHONW_EXE="

rem Buscar Python 3.9+
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
  if not errorlevel 1 set "PYTHON_EXE=py -3"
)
if not defined PYTHON_EXE (
  where python >nul 2>nul
  if not errorlevel 1 (
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
    if not errorlevel 1 set "PYTHON_EXE=python"
  )
)
if not defined PYTHON_EXE (
  echo ERROR: No se encontro Python 3.9+. Instalalo o anade al PATH.
  pause
  exit /b 1
)

for /f "tokens=*" %%A in ('%PYTHON_EXE% -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%A"
for %%A in ("%PYTHON_EXE%") do set "PYTHON_DIR=%%~dpA"
set "PYTHONW_EXE=%PYTHON_DIR%pythonw.exe"
if not exist "%PYTHONW_EXE%" set "PYTHONW_EXE=%PYTHON_EXE%"

echo Python:  %PYTHON_EXE%
echo Pythonw: %PYTHONW_EXE%
echo Proyecto: %PROJECT_DIR%
echo Script:   %SCRIPT%
echo Inicio:   %VBS%

rem Verificar e instalar watchdog
%PYTHON_EXE% -c "import watchdog" >nul 2>nul
if errorlevel 1 (
  echo Instalando watchdog...
  %PYTHON_EXE% -m pip install --quiet watchdog
  if errorlevel 1 (
    echo ERROR: No se pudo instalar watchdog.
    pause
    exit /b 1
  )
)

rem Crear el lanzador oculto en la carpeta Inicio
if not exist "%STARTUP_DIR%" (
  echo ERROR: No existe la carpeta Inicio: %STARTUP_DIR%
  pause
  exit /b 1
)

> "%VBS%" echo Set sh = CreateObject("WScript.Shell")
>> "%VBS%" echo sh.Run """%PYTHONW_EXE%"" ""%SCRIPT%"" run", 0, False

if not exist "%VBS%" (
  echo ERROR: No se pudo crear %VBS%
  pause
  exit /b 1
)

echo.
echo OK: Instalado en la carpeta Inicio.
echo Se ejecutara automaticamente al iniciar sesion.

rem Arrancarlo ahora mismo
echo Arrancando ahora...
start "" "%PYTHONW_EXE%" "%SCRIPT%" run
timeout /t 2 /nobreak >nul

echo.
echo Estado:
%PYTHON_EXE% "%SCRIPT%" status
echo.
echo Log: %PROJECT_DIR%logs\registro_cambios\cambios_YYYY-WWW.log
echo Para ver:      vigilante_cambios.bat ver 50
echo Para parar:    vigilante_cambios.bat stop
echo Para borrar:   desinstalar_vigilante.bat
echo.
pause