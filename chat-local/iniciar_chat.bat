@echo off
setlocal
cd /d "%~dp0"

REM Inicia el chat con el mismo script que usa start.bat: espera a que el
REM servidor responda y solo entonces abre el navegador.
set "PYEXE="
if exist "%~dp0..\runtime\python\python.exe" (
    if not exist "%~dp0..\logs" mkdir "%~dp0..\logs" >nul 2>nul
    "%~dp0..\runtime\python\python.exe" -c "import pathlib,sys; p=pathlib.Path(sys.argv[1]); p.write_text('ok'); p.unlink()" "%~dp0..\logs\.py_write_test" >nul 2>nul
    if not errorlevel 1 set "PYEXE=%~dp0..\runtime\python\python.exe"
)
if not defined PYEXE (
    for /f "delims=" %%P in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "PYEXE=%%P"
)
if not defined PYEXE (
    for /f "delims=" %%P in ('python -c "import sys;print(sys.executable)" 2^>nul') do set "PYEXE=%%P"
)
if not defined PYEXE (
    echo No se encontro Python 3 ni runtime\python\python.exe. Ejecuta preparar_portable.bat o instala Python 3.9+.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0lanzar_chat.ps1" -PythonExe "%PYEXE%"
set "CHAT_EXIT=%errorlevel%"
if not "%CHAT_EXIT%"=="0" pause
exit /b %CHAT_EXIT%
