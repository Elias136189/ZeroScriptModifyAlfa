@echo off
setlocal
cd /d "%~dp0"

REM Solo se activa con un comando explicito:
REM   despertar.bat /opencode      -> OpenCode (CLI)
REM   despertar.bat /antigravity   -> Antigravity (ventana)
REM   despertar.bat /claude-code   -> Claude Code (CLI)
REM   despertar.bat /codex         -> Codex (CLI)
REM   despertar.bat /todos         -> todos los destinos activos en despertar_config.json
REM   despertar.bat /<destino>     -> cualquier otro destino configurado en despertar_config.json
REM   despertar.bat /estado        -> muestra estado, presupuesto y destinos
REM   despertar.bat /claude        -> solo estado; Claude Desktop gratis no se despierta
REM Segundo argumento opcional: /simular = muestra que haria, sin activar nada.

set "RAW=%~1"
if not defined RAW goto ayuda
if "%RAW:~0,1%"=="/" set "RAW=%RAW:~1%"
if not defined RAW goto ayuda

if /i "%RAW%"=="?" goto ayuda
if /i "%RAW%"=="help" goto ayuda
if /i "%RAW%"=="-h" goto ayuda
if /i "%RAW%"=="--help" goto ayuda

set "ARGS="
if /i "%RAW%"=="estado" set "ARGS=--status"
if /i "%RAW%"=="status" set "ARGS=--status"
if /i "%RAW%"=="lista" set "ARGS=--list-targets"
if /i "%RAW%"=="destinos" set "ARGS=--list-targets"
if defined ARGS goto ejecutar

set "TARGET=%RAW%"
if /i "%RAW%"=="todos" set "TARGET=*"
if /i "%RAW%"=="all" set "TARGET=*"

set "APPLY=--apply"
if /i "%~2"=="/simular" set "APPLY="
if /i "%~2"=="--simular" set "APPLY="
if /i "%TARGET%"=="claude" goto manual

set "ARGS=%TARGET% %APPLY%"
goto ejecutar

:manual
echo   Claude Desktop con cuenta gratis no se despierta; se muestra el estado.
set "ARGS=claude"
goto ejecutar

:ayuda
echo.
echo   despertar.bat no activa nada sin un comando.
echo.
echo     despertar.bat /opencode      despierta a OpenCode
echo     despertar.bat /antigravity   despierta a Antigravity
echo     despertar.bat /claude-code   despierta a Claude Code
echo     despertar.bat /codex         despierta a Codex
echo     despertar.bat /todos         despierta todos los destinos activos
echo     despertar.bat /estado        muestra estado y destinos configurados
echo     despertar.bat /claude        solo muestra el estado, no se despierta
echo     agrega /simular al final para ver que haria sin activar
echo.
echo   Tambien acepta cualquier otro destino definido en despertar_config.json.
echo   Solo se despierta si el mensaje lleva @despertar o [despertar].
echo.
exit /b 1

:ejecutar
if exist "%~dp0runtime\python\python.exe" (
  if not exist "%~dp0logs" mkdir "%~dp0logs" >nul 2>nul
  "%~dp0runtime\python\python.exe" -c "import pathlib,sys; p=pathlib.Path(sys.argv[1]); p.write_text('ok'); p.unlink()" "%~dp0logs\.py_write_test" >nul 2>nul
  if not errorlevel 1 goto con_portable
)
where py >nul 2>nul
if %ERRORLEVEL%==0 goto con_py
python "%~dp0despertar.py" %ARGS%
exit /b %ERRORLEVEL%

:con_portable
"%~dp0runtime\python\python.exe" "%~dp0despertar.py" %ARGS%
exit /b %ERRORLEVEL%

:con_py
py -3 "%~dp0despertar.py" %ARGS%
exit /b %ERRORLEVEL%
