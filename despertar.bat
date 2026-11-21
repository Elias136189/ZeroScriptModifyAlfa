@echo off
setlocal
cd /d "%~dp0"

REM Solo se activa con un comando explicito:
REM   despertar.bat /opencode   -> OpenCode (automatico)
REM   despertar.bat /claude     -> solo estado; Claude gratis no se despierta
REM Segundo argumento opcional: /simular = muestra que haria, sin activar nada.
REM Sin comando no hace nada. Los limites y el archivo wake_off siguen
REM funcionando porque los aplica despertar.py.
set "TARGET="
if /i "%~1"=="/claude" set "TARGET=claude"
if /i "%~1"=="/opencode" set "TARGET=opencode"
if not defined TARGET goto ayuda

set "APPLY=--apply"
if /i "%~2"=="/simular" set "APPLY="
if /i "%TARGET%"=="claude" goto manual

goto ejecutar

:manual
echo   Claude Desktop con cuenta gratis no se despierta; se muestra el estado.
set "APPLY="
goto ejecutar

:ayuda
echo.
echo   despertar.bat no activa nada sin un comando.
echo.
echo     despertar.bat /opencode   despierta a OpenCode
echo     despertar.bat /claude     solo muestra el estado, no se despierta
echo     agrega /simular al final para ver que haria sin activar
echo.
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
python "%~dp0despertar.py" %TARGET% %APPLY%
exit /b %ERRORLEVEL%

:con_portable
"%~dp0runtime\python\python.exe" "%~dp0despertar.py" %TARGET% %APPLY%
exit /b %ERRORLEVEL%

:con_py
py -3 "%~dp0despertar.py" %TARGET% %APPLY%
exit /b %ERRORLEVEL%
