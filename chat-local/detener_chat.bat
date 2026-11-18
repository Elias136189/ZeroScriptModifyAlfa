@echo off
setlocal
cd /d "%~dp0"

REM Detiene el servidor del chat local arrancado por lanzar_chat.ps1.
REM Uso: detener_chat.bat [puerto]   (por defecto 8765)
set "CHAT_PORT=%~1"
if not defined CHAT_PORT set "CHAT_PORT=8765"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0lanzar_chat.ps1" -Stop -Port %CHAT_PORT%
exit /b %errorlevel%
