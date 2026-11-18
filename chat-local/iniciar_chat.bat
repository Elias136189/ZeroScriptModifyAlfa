@echo off
setlocal
cd /d "%~dp0"

REM Inicia el chat con el mismo script que usa start.bat: espera a que el
REM servidor responda y solo entonces abre el navegador.
set "PYEXE="
for /f "delims=" %%P in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "PYEXE=%%P"
if not defined PYEXE (
    echo No se encontro Python 3. Instala Python 3.9 o superior.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0lanzar_chat.ps1" -PythonExe "%PYEXE%"
set "CHAT_EXIT=%errorlevel%"
if not "%CHAT_EXIT%"=="0" pause
exit /b %CHAT_EXIT%
