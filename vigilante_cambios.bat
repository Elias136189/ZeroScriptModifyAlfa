:: SPDX-License-Identifier: GPL-3.0-or-later
@echo off
:: Lanzador del vigilante de cambios. Ejemplos:
::   vigilante_cambios.bat start      arranca en segundo plano
::   vigilante_cambios.bat stop       lo detiene
::   vigilante_cambios.bat status     estado y ultimos eventos
::   vigilante_cambios.bat ver 50     ultimas 50 lineas del registro
setlocal
cd /d "%~dp0"
set "PY=python"
where py >nul 2>nul && set "PY=py -3"
%PY% "%~dp0vigilante_cambios.py" %*
exit /b %errorlevel%
