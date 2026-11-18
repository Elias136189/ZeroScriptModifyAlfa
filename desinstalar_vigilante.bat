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
py -3 "%SCRIPT%" stop 2>nul
if errorlevel 1 python "%SCRIPT%" stop 2>nul

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