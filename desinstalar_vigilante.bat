@echo off
setlocal

rem ============================================================
rem Desinstala el vigilante de cambios:
rem   1. detiene el proceso en segundo plano
rem   2. borra el lanzador de la carpeta Inicio
rem   3. borra una tarea programada si existiera
rem ============================================================

set "PROJECT_DIR=%~dp0"
set "SCRIPT=%PROJECT_DIR%vigilante_cambios.py"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "VBS=%STARTUP_DIR%\ZeroScript_Vigilante_Cambios.vbs"
set "TASK_NAME=ZeroScript_Vigilante_Cambios"

echo Deteniendo el vigilante...
set "STOPPED_WITH_PORTABLE=0"
if exist "%PROJECT_DIR%runtime\python\python.exe" (
  if not exist "%PROJECT_DIR%logs" mkdir "%PROJECT_DIR%logs" >nul 2>nul
  "%PROJECT_DIR%runtime\python\python.exe" -c "import pathlib,sys; p=pathlib.Path(sys.argv[1]); p.write_text('ok'); p.unlink()" "%PROJECT_DIR%logs\.py_write_test" >nul 2>nul
  if not errorlevel 1 (
    "%PROJECT_DIR%runtime\python\python.exe" "%SCRIPT%" stop 2>nul
    set "STOPPED_WITH_PORTABLE=1"
  )
)
if "%STOPPED_WITH_PORTABLE%"=="0" (
  py -3 "%SCRIPT%" stop 2>nul
  if errorlevel 1 python "%SCRIPT%" stop 2>nul
)

echo Borrando lanzador de Inicio...
if exist "%VBS%" (
  del /f /q "%VBS%"
  echo   Borrado: %VBS%
) else (
  echo   No existia: %VBS%
)

echo Borrando tarea programada (si existia)...
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>nul
if errorlevel 1 (
  echo   No habia tarea programada.
) else (
  echo   Tarea borrada.
)

echo.
echo Listo.
pause