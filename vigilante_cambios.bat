:: SPDX-License-Identifier: GPL-3.0-or-later
@echo off
:: Lanzador del vigilante de cambios. Ejemplos:
::   vigilante_cambios.bat start      arranca en segundo plano
::   vigilante_cambios.bat stop       lo detiene
::   vigilante_cambios.bat status     estado y ultimos eventos
::   vigilante_cambios.bat ver 50     ultimas 50 lineas del registro
setlocal
cd /d "%~dp0"
set "PY="
if exist "%~dp0runtime\python\python.exe" (
    if not exist "%~dp0logs" mkdir "%~dp0logs" >nul 2>nul
    "%~dp0runtime\python\python.exe" -c "import pathlib,sys; p=pathlib.Path(sys.argv[1]); p.write_text('ok'); p.unlink()" "%~dp0logs\.py_write_test" >nul 2>nul
    if not errorlevel 1 set PY="%~dp0runtime\python\python.exe"
)
if not defined PY (
    where py >nul 2>nul && set "PY=py -3"
)
if not defined PY set "PY=python"
call %PY% "%~dp0vigilante_cambios.py" %*
exit /b %errorlevel%
