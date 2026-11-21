:: SPDX-License-Identifier: GPL-3.0-or-later
@echo off
setlocal
cd /d "%~dp0"

echo.
echo   === ZeroScript - Preparar Python Portable ===
echo.
echo   Descarga Python 3.12 oficial en runtime\python\ e instala
echo   websockets y watchdog dentro de esta misma carpeta.
echo   No instala nada en Windows ni requiere permisos de administrador.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0preparar_portable.ps1" %*
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
    echo   ERROR: no se pudo preparar el entorno portable ^(codigo %RC%^).
    echo   Revisa tu conexion a internet o el antivirus.
) else (
    echo   OK: proyecto listo para copiarse a cualquier PC sin Python.
)
echo.
if /i not "%~1"=="/nopause" pause
exit /b %RC%
