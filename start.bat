:: SPDX-License-Identifier: GPL-3.0-or-later
@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title ZeroScript Bridge
cd /d "%~dp0"

set "ROOT=%~dp0"
if not defined ZS_BRIDGE_PORT set "ZS_BRIDGE_PORT=17613"
if not defined CHAT_LOCAL_PORT set "CHAT_LOCAL_PORT=8765"

REM Opciones de linea de comandos:
REM   start.bat /nochat    -> no abre el chat local en el navegador
set "OPT_NOCHAT=0"
:parse_args
if "%~1"=="" goto :args_done
if /i "%~1"=="/nochat"  set "OPT_NOCHAT=1"
shift
goto :parse_args
:args_done

REM El ID de la extension ya se fija automaticamente en bridge.py usando el
REM campo "key" de zeroscript-extension\manifest.json (o la ruta actual si no
REM tiene "key"). Si necesitas forzar otro ID, define ZS_BRIDGE_EXTENSION_ID.

REM Preparar carpetas y configuraciones iniciales con rutas relativas si faltan
if not exist "%ROOT%workspace_wake" mkdir "%ROOT%workspace_wake" >nul 2>nul
if not exist "%ROOT%pc_agent_config.json" if exist "%ROOT%pc_agent_config.example.json" copy /y "%ROOT%pc_agent_config.example.json" "%ROOT%pc_agent_config.json" >nul 2>nul
if not exist "%ROOT%pc_agent_config.restricted.json" if exist "%ROOT%pc_agent_config.restricted.example.json" copy /y "%ROOT%pc_agent_config.restricted.example.json" "%ROOT%pc_agent_config.restricted.json" >nul 2>nul
if not exist "%ROOT%despertar_config.json" if exist "%ROOT%despertar_config.example.json" copy /y "%ROOT%despertar_config.example.json" "%ROOT%despertar_config.json" >nul 2>nul

if not exist "%ROOT%logs" mkdir "%ROOT%logs" >nul 2>nul
set "LOGFILE=%ROOT%logs\start.log"
call :log "===== %DATE% %TIME%  start.bat launched ====="
for /f "tokens=*" %%v in ('ver') do call :log "%%v"

echo.
echo   === ZeroScript Bridge ===
echo.

if not exist "%ROOT%bridge.py" goto :err_no_bridge

REM --- 1. Arranque con Python embebido (runtime\python\) ---------------------
echo   [1/3] Comprobando Python embebido ^(runtime\python^)...
set "PY_EXE="
set "PYW_EXE="
set "PY_MODE="
set "PORTABLE_PY=%ROOT%runtime\python\python.exe"
set "PORTABLE_PYW=%ROOT%runtime\python\pythonw.exe"
set "PORTABLE_CFA_BLOCKED=0"

if not exist "%PORTABLE_PY%" goto :bootstrap_portable
"%PORTABLE_PY%" -c "import sys, websockets; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
if errorlevel 1 goto :bootstrap_portable
goto :check_portable_write

:bootstrap_portable
if not exist "%ROOT%preparar_portable.ps1" goto :fallback_system
echo         Preparando Python 3.12 embebido en runtime\python\ ^(primera vez^)...
call :log "Embedded Python missing or incomplete; running preparar_portable.ps1."
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%preparar_portable.ps1"
if errorlevel 1 goto :bootstrap_failed
if not exist "%PORTABLE_PY%" goto :bootstrap_failed
goto :check_portable_write

:bootstrap_failed
echo         AVISO: no se pudo preparar runtime\python\ automaticamente.
call :log "preparar_portable.ps1 failed; trying system Python as fallback."
goto :fallback_system

:check_portable_write
"%PORTABLE_PY%" -c "import sys, websockets; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
if errorlevel 1 goto :fallback_system

REM Comprobar si Windows Defender (Acceso controlado a carpetas) bloquea escribir en logs\
"%PORTABLE_PY%" -c "import pathlib, sys; p = pathlib.Path(sys.argv[1]); p.write_text('ok', encoding='ascii'); p.unlink()" "%ROOT%logs\.py_write_test" >nul 2>nul
if errorlevel 1 goto :portable_cfa_blocked

set "PY_EXE=%PORTABLE_PY%"
if exist "%PORTABLE_PYW%" set "PYW_EXE=%PORTABLE_PYW%"
set "PY_MODE=embebido"
set "PYTHONDONTWRITEBYTECODE=1"
goto :python_ready

:portable_cfa_blocked
set "PORTABLE_CFA_BLOCKED=1"
echo         AVISO: Windows Defender ^(Acceso controlado a carpetas^) bloqueo la
echo                escritura de runtime\python\python.exe en esta carpeta.
echo                Buscando Python del sistema como respaldo...
call :log "Embedded Python blocked from writing to logs\ (Defender CFA); checking system Python."

:fallback_system
call :try_sys_cmd "py -3"
if defined PY_EXE goto :sys_found
call :try_sys_cmd "python"
if defined PY_EXE goto :sys_found
for %%R in ("%LOCALAPPDATA%\Programs\Python" "%ProgramFiles%" "%ProgramFiles(x86)%") do (
    if not defined PY_EXE if exist "%%~R" (
        for /f "delims=" %%D in ('dir /b /ad /o-n "%%~R\Python3*" 2^>nul') do (
            if not defined PY_EXE if exist "%%~R\%%D\python.exe" (
                call :try_sys_exe "%%~R\%%D\python.exe"
            )
        )
    )
)
if defined PY_EXE goto :sys_found
goto :err_no_python

:sys_found
set "PY_MODE=sistema (respaldo)"
for %%P in ("%PY_EXE%") do if exist "%%~dpPpythonw.exe" set "PYW_EXE=%%~dpPpythonw.exe"
goto :python_ready

:python_ready
set "PY_VER="
for /f "tokens=*" %%v in ('"%PY_EXE%" --version 2^>^&1') do set "PY_VER=%%v"
echo         Python [!PY_MODE!]: !PY_VER!
echo         Ruta: !PY_EXE!
call :log "Python selected [!PY_MODE!]: !PY_EXE! [!PY_VER!]"

REM --- 2. Verificar libreria websockets --------------------------------------
echo.
echo   [2/3] Comprobando libreria websockets...
"%PY_EXE%" -c "import websockets" >nul 2>nul
if not errorlevel 1 goto :deps_ok

if /i "%PY_MODE%"=="embebido" goto :repair_portable_deps
echo         Instalando websockets en Python del sistema...
"%PY_EXE%" -m pip install --user websockets
if errorlevel 1 goto :err_no_websockets
goto :deps_ok

:repair_portable_deps
echo         Reparando websockets en runtime\python\...
call :log "websockets missing in embedded Python; running preparar_portable.ps1."
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%preparar_portable.ps1" -Force
"%PY_EXE%" -c "import websockets" >nul 2>nul
if errorlevel 1 goto :err_no_websockets

:deps_ok
echo         OK
call :log "websockets library OK"

REM --- 3. Arrancar chat local y bridge ---------------------------------------
echo.
echo   [3/3] Iniciando bridge ^(puerto %ZS_BRIDGE_PORT%^)...

set "OLDPID="
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":%ZS_BRIDGE_PORT% " ^| findstr LISTENING 2^>nul') do (
    set "OLDPID=%%a"
)
if not defined OLDPID goto :port_free

REM Comprobar que el proceso en el puerto realmente es bridge.py antes de cerrarlo
set "IS_BRIDGE=0"
for /f "usebackq tokens=*" %%C in (`powershell -NoProfile -Command "$f='ProcessId='+$env:OLDPID; $p=Get-CimInstance Win32_Process -Filter $f -EA 0; $p.CommandLine -like '*bridge.py*'" 2^>nul`) do (
    if /i "%%C"=="True" set "IS_BRIDGE=1"
)
if "%IS_BRIDGE%"=="0" goto :port_other_app

echo         Bridge anterior detectado ^(pid !OLDPID!^). Reiniciando...
call :log "Killing previous bridge instance - pid !OLDPID! - port %ZS_BRIDGE_PORT%."
taskkill /F /T /PID !OLDPID! >nul 2>nul
ping -n 2 127.0.0.1 >nul 2>nul
set "STILLTHERE="
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":%ZS_BRIDGE_PORT% " ^| findstr LISTENING 2^>nul') do (
    set "STILLTHERE=%%a"
)
if defined STILLTHERE (
    echo   AVISO: el puerto %ZS_BRIDGE_PORT% sigue ocupado por pid !STILLTHERE!.
    call :log "WARNING: port %ZS_BRIDGE_PORT% still held by pid !STILLTHERE! after taskkill."
)
goto :port_free

:port_other_app
echo.
echo   ERROR: el puerto %ZS_BRIDGE_PORT% esta ocupado por otro programa ^(pid !OLDPID!^),
echo   no por bridge.py. Cierra ese programa o define otro puerto con ZS_BRIDGE_PORT.
echo.
call :log "FATAL: port %ZS_BRIDGE_PORT% held by non-bridge pid !OLDPID!."
goto :finish_fail

:port_free
echo.
echo  ############################################################
echo  ##                                                        ##
echo  ##   MANTEN ESTA VENTANA ABIERTA mientras uses ZeroScript ##
echo  ##   Si cierras esta ventana ^(X o Ctrl+C^), todo el        ##
echo  ##   bridge, MCP y chat local se apagan automaticamente.  ##
echo  ##                                                        ##
echo  ############################################################
echo.

if "%OPT_NOCHAT%"=="0" (
    set "ZS_STOP_CHAT_ON_EXIT=1"
    call :start_chat
) else (
    set "ZS_STOP_CHAT_ON_EXIT=0"
)
call :check_despertar
call :ensure_vigilante

set "ZS_MANAGED_BY_START_BAT=1"
:run_bridge
call :log "Running bridge.py in foreground with !PY_EXE!"
"!PY_EXE!" "%ROOT%bridge.py"
set "BR_EXIT=%errorlevel%"
if "%BR_EXIT%"=="42" (
    echo.
    echo   Reiniciando bridge con la nueva configuracion...
    call :log "bridge.py requested reload (exit 42); restarting in same console."
    goto :run_bridge
)

if "%OPT_NOCHAT%"=="0" if exist "%ROOT%chat-local\lanzar_chat.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%chat-local\lanzar_chat.ps1" -Port %CHAT_LOCAL_PORT% -Stop >nul 2>nul
)
call :log "start.bat finished (bridge exit !BR_EXIT!)."
exit /b %BR_EXIT%

REM --- Errores fatales -------------------------------------------------------
:err_no_bridge
echo   ERROR: bridge.py no se encontro junto a start.bat.
echo.
echo   Si abriste start.bat desde dentro del ZIP, primero EXTRAE toda la carpeta
echo   ^(clic derecho, "Extraer todo..."^) y ejecuta start.bat desde la carpeta extraida.
echo.
call :log "FATAL: bridge.py missing next to start.bat."
goto :finish_fail

:err_no_python
echo.
if "%PORTABLE_CFA_BLOCKED%"=="1" (
    echo   ERROR: runtime\python\python.exe existe, pero Windows Defender ^(Acceso
    echo   controlado a carpetas^) impide que escriba dentro de esta ruta y no hay
    echo   Python del sistema instalado.
    echo.
    echo   Soluciones:
    echo     1. Mueve esta carpeta fuera de Documentos ^(ej. C:\ZeroScriptModify^)
    echo     2. O permite runtime\python\python.exe en Seguridad de Windows.
) else (
    echo   ERROR: no se pudo iniciar Python embebido ^(runtime\python\^) ni se encontro
    echo   Python 3.9+ en este PC.
    echo.
    echo   Con conexion a internet, ejecuta preparar_portable.bat para descargar
    echo   Python 3.12 embebido en runtime\python\, o copia la carpeta runtime\ desde otro PC.
)
echo.
call :log "FATAL: no usable embedded or system Python found."
goto :finish_fail

:err_no_websockets
echo.
echo   ERROR: no se pudo cargar ni instalar la libreria websockets.
echo   Comprueba tu conexion a internet o ejecuta preparar_portable.bat.
echo.
call :log "FATAL: websockets unavailable."
goto :finish_fail

:finish_fail
exit /b 1

REM --- Subrutinas ------------------------------------------------------------
:try_sys_cmd
set "CAND_CMD=%~1"
set "CAND_EXE="
for /f "delims=" %%P in ('%CAND_CMD% -c "import sys; print(sys.executable) if sys.version_info >= (3, 9) else sys.exit(1)" 2^>nul') do set "CAND_EXE=%%P"
if not defined CAND_EXE exit /b 1
echo !CAND_EXE! | findstr /i "WindowsApps" >nul && exit /b 1
call :try_sys_exe "!CAND_EXE!"
exit /b %errorlevel%

:try_sys_exe
set "CAND_PATH=%~1"
if not exist "%CAND_PATH%" exit /b 1
"%CAND_PATH%" -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul || exit /b 1
"%CAND_PATH%" -c "import websockets" >nul 2>nul && (
    set "PY_EXE=%CAND_PATH%"
    exit /b 0
)
"%CAND_PATH%" -m pip --version >nul 2>nul || exit /b 1
set "PY_EXE=%CAND_PATH%"
exit /b 0

:log
>>"%LOGFILE%" 2>nul echo(%~1
exit /b 0

:start_chat
if not exist "%ROOT%chat-local\server.py" (
    call :log "Chat local: server.py not found; browser not opened."
    exit /b 0
)
if not exist "%ROOT%chat-local\chat.html" (
    call :log "Chat local: chat.html not found; browser not opened."
    exit /b 0
)
if not exist "%ROOT%chat-local\lanzar_chat.ps1" (
    call :log "Chat local: lanzar_chat.ps1 not found; browser not opened."
    exit /b 0
)
start "" /b powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%chat-local\lanzar_chat.ps1" -PythonExe "!PY_EXE!" -Port %CHAT_LOCAL_PORT% >nul 2>nul
echo         Chat local: comprobando http://127.0.0.1:%CHAT_LOCAL_PORT%
call :log "Chat local: launcher started with '!PY_EXE!' on port %CHAT_LOCAL_PORT%."
exit /b 0

:check_despertar
if not exist "%ROOT%despertar.bat" (
    call :log "Despertar: despertar.bat not found."
    exit /b 0
)
if not exist "%ROOT%despertar.py" (
    call :log "Despertar: despertar.py not found."
    exit /b 0
)
echo.
echo         Mensajero listo ^(el bridge lo arranca automaticamente^):
echo           despertar.bat /opencode   - OpenCode ^(automatico^)
echo           despertar.bat /claude     - Claude ^(solo estado; no se despierta^)
echo           solo despierta si el mensaje lleva @despertar o [despertar]
echo           ^(agrega /simular para probar sin activar; crea wake_off para apagarlo^)
if exist "%ROOT%wake_off" echo         AVISO: existe wake_off, el mensajero esta apagado.
call :log "Despertar: OpenCode automatic; Claude manual; token @despertar."
exit /b 0

:ensure_vigilante
if not exist "%ROOT%vigilante_cambios.py" (
    call :log "Vigilante: vigilante_cambios.py not found."
    exit /b 0
)
set "VIG_STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\ZeroScript_Vigilante_Cambios.vbs"
if defined ZS_VIGILANTE_STARTUP_DIR set "VIG_STARTUP=%ZS_VIGILANTE_STARTUP_DIR%\ZeroScript_Vigilante_Cambios.vbs"
if exist "!VIG_STARTUP!" (
    echo         Vigilante: PC ya tiene el vigilante instalado ^(no se reinstala^).
    call :log "Vigilante: already installed on this PC (!VIG_STARTUP!); skipping auto-install."
    exit /b 0
)
echo         Vigilante: nueva PC detectada; instalando en Inicio y arrancando...
call :log "Vigilante: new PC detected; installing Startup VBS and starting watcher."
"!PY_EXE!" -c "import watchdog" >nul 2>nul
if errorlevel 1 (
    if /i not "%PY_MODE%"=="embebido" (
        "!PY_EXE!" -m pip install --user --quiet watchdog >nul 2>nul
    )
)
"!PY_EXE!" "%ROOT%vigilante_cambios.py" ensure
call :log "Vigilante: ensure finished with exit !errorlevel!."
exit /b 0
