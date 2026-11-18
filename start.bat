:: SPDX-License-Identifier: GPL-3.0-or-later
@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title ZeroScript Bridge
cd /d "%~dp0"

REM Pin the Chrome extension ID so the bridge only accepts connections from
REM the ZeroScript extension, not any arbitrary extension (security fix).
if not defined ZS_BRIDGE_EXTENSION_ID set "ZS_BRIDGE_EXTENSION_ID=ljkcldlijdibhfookemkeeefpmgijcge"

if not exist "%~dp0logs" mkdir "%~dp0logs" >nul 2>nul
set "LOGFILE=%~dp0logs\start.log"
call :log "===== %DATE% %TIME%  start.bat launched ====="
REM Log the Windows build once per launch - most support requests arrive as a
REM single terminal screenshot, so anything that identifies the machine's
REM environment must be either ON SCREEN or in this log.
for /f "tokens=*" %%v in ('ver') do call :log "%%v"

echo.
echo   === ZeroScript Bridge ===
echo.

REM Refuse to run from inside a ZIP preview: Explorer extracts start.bat alone
REM to %TEMP%, so bridge.py is missing and the launch fails with a confusing
REM Python error. Detect the missing file up front with a plain explanation -
REM this is one of the most common first-run mistakes.
if not exist "%~dp0bridge.py" (
    echo   ERROR: bridge.py not found next to start.bat.
    echo.
    echo   If you opened start.bat from inside the downloaded ZIP, first EXTRACT
    echo   the whole ZIP ^(right-click, "Extract All..."^), then run start.bat
    echo   from the extracted folder.
    echo.
    call :log "FATAL: bridge.py missing next to start.bat - run from inside ZIP?"
    pause
    exit /b 1
)

REM --- 1. Find Python ---------------------------------------------------------
echo   [1/3] Looking for Python...
set "PY="

REM Prefer the py launcher - it never resolves to the Microsoft Store stub.
where py >nul 2>nul && set "PY=py -3"
call :validate_py && goto :found

REM Fall back to python on PATH, but skip the Store stub (WindowsApps) which
REM cannot run pip and silently fails.
set "PY=python"
call :validate_py && goto :found

REM Last resort: scan the standard install folders directly. Covers the common
REM case where Python was installed WITHOUT "Add to PATH" and without the py
REM launcher, so neither "py" nor "python" resolves. Newest version first.
for %%R in (
    "%LOCALAPPDATA%\Programs\Python"
    "%ProgramFiles%"
    "%ProgramFiles(x86)%"
) do (
    if exist "%%~R" (
        for /f "delims=" %%D in ('dir /b /ad /o-n "%%~R\Python3*" 2^>nul') do (
            if exist "%%~R\%%D\python.exe" (
                set PY="%%~R\%%D\python.exe"
                call :validate_py && goto :found
            )
        )
    )
)

set "PY="
call :log "Python not found on PATH or in standard install folders."
goto :need_install

:found
REM Print the exact interpreter VERSION on screen (not just the launcher name):
REM a user screenshot must tell us whether the failure is a too-old Python
REM without asking them to run anything else.
REM "call" prefix: when %PY% is a quoted full path (the no-PATH scan case), a
REM bare quoted command inside for /f trips cmd's leading-quote stripping rule;
REM call re-parses the line and keeps the quotes intact.
for /f "tokens=*" %%v in ('call %PY% --version 2^>^&1') do (
    echo         Found: %PY%  ^(%%v^)
    call :log "Python found: %PY% [%%v]"
)

REM --- Resolve actual python.exe path (not py launcher) for pip install ---
set "PY_EXE="
for /f "delims=" %%P in ('call %PY% -c "import sys; print(sys.executable)" 2^>nul') do set "PY_EXE=%%P"
if not defined PY_EXE (
    REM Fallback: if PY is already a full path
    for %%P in ("%PY%") do if exist "%%~fP" set "PY_EXE=%%~fP"
)
if defined PY_EXE (
    echo         Resolved python.exe: %PY_EXE%
    call :log "Resolved python.exe for pip: %PY_EXE%"
)

REM --- Find pythonw.exe (windowless) for launching the bridge hidden ---
set "PYW="
if defined PY (
    REM If PY is "py -3" or "python", try to find pythonw.exe via py launcher
    for /f "delims=" %%P in ('call %PY% -c "import sys; import os; print(os.path.join(os.path.dirname(sys.executable), 'pythonw.exe'))" 2^>nul') do set "PYW=%%P"
)
if not defined PYW (
    REM Fallback: if PY is a full path to python.exe, replace with pythonw.exe
    for %%P in ("%PY%") do if exist "%%~dpPpythonw.exe" set "PYW=%%~dpPpythonw.exe"
)
if not defined PYW (
    REM Last resort: common locations
    for %%R in ("%LOCALAPPDATA%\Programs\Python" "%ProgramFiles%" "%ProgramFiles(x86)%") do (
        if exist "%%~R" (
            for /f "delims=" %%D in ('dir /b /ad /o-n "%%~R\Python3*" 2^>nul') do (
                if exist "%%~R\%%D\pythonw.exe" set "PYW=%%~R\%%D\pythonw.exe"
            )
        )
    )
)
if defined PYW (
    echo         Found pythonw.exe for hidden launch
    call :log "pythonw.exe found: %PYW%"
) else (
    echo         ADVERTENCIA: pythonw.exe no encontrado; el bridge se vera en consola
    call :log "WARNING: pythonw.exe not found, bridge will show console"
)
goto :install_deps

:need_install
REM --- Python not found, try winget -------------------------------------------
REM winget itself may be absent (LTSC / old Win10 / stripped installs). Without
REM this check the "winget" line fails with an unrelated "not recognized" error
REM that users screenshot without context - name the real problem instead.
where winget >nul 2>nul
if errorlevel 1 (
    echo   ERROR: Python is not installed and winget ^(Windows package manager^)
    echo   is not available on this PC, so it cannot be installed automatically.
    echo.
    echo   Install Python manually: https://www.python.org/downloads/
    echo   IMPORTANT: tick "Add python.exe to PATH", then run start.bat again.
    echo.
    call :log "FATAL: no Python and no winget on this machine."
    pause
    exit /b 1
)
echo         Not found. Installing via winget...
echo.
winget install --id Python.Python.3.12 --source winget --accept-package-agreements --accept-source-agreements
if errorlevel 1 call :log "winget install returned an error - see console output above."
echo.
echo   Checking again...
set "PY=py -3"
call :validate_py && goto :ready
set "PY=python"
call :validate_py && goto :ready
REM A winget install does NOT refresh THIS console's PATH, so "py"/"python" can
REM stay unresolvable in the very session that installed them. Rescan the
REM standard install folders directly (same scan as the pre-install fallback)
REM before telling the user it failed - a plain restart-and-retry would have
REM worked, so we do its equivalent for them.
for %%R in (
    "%LOCALAPPDATA%\Programs\Python"
    "%ProgramFiles%"
    "%ProgramFiles(x86)%"
) do (
    if exist "%%~R" (
        for /f "delims=" %%D in ('dir /b /ad /o-n "%%~R\Python3*" 2^>nul') do (
            if exist "%%~R\%%D\python.exe" (
                set PY="%%~R\%%D\python.exe"
                call :validate_py && goto :ready
            )
        )
    )
)
echo.
echo   ERROR: Python not found after install.
echo   Install manually: https://www.python.org/downloads/
echo   Tick "Add python.exe to PATH" then run this again.
echo.
call :log "FATAL: no usable Python found even after winget install."
pause
exit /b 1
:ready
echo         Python ready!
call :log "Python ready after winget install: %PY%"

:install_deps
REM --- 2. Install websockets --------------------------------------------------
echo.
echo   [2/3] Checking websockets library...
%PY% -c "import websockets" >nul 2>nul
if errorlevel 1 (
    echo         Installing websockets - first time only...
    %PY% -c "import subprocess, sys; subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--user', 'websockets'])"
    if errorlevel 1 (
        echo.
        echo   ERROR: Could not install websockets ^(see pip output above^).
        echo   Common causes: no internet, a firewall/antivirus blocking pip,
        echo   or Python has no working pip. If you used the Microsoft Store
        echo   python, install from https://www.python.org/downloads/ instead
        echo   ^(tick "Add to PATH"^).
        echo.
        call :log "FATAL: pip install websockets failed."
        pause
        exit /b 1
    )
)
echo         OK
call :log "websockets library OK"

REM --- 3. Run the bridge ------------------------------------------------------
echo.
echo   [3/3] Starting bridge...

REM If a previous bridge is already listening on 17613, say so instead of
REM silently killing it - a double-launch is easy to do by mistake (e.g.
REM double-clicking start.bat twice) and should not look like nothing happened.
set "OLDPID="
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :17613 ^| findstr LISTENING 2^>nul') do (
    set "OLDPID=%%a"
)
if defined OLDPID (
    echo         A previous bridge ^(pid !OLDPID!^) is already running on this port.
    echo         Replacing it with this new instance...
    call :log "Killing previous bridge instance - pid !OLDPID! - port 17613."
    taskkill /F /T /PID !OLDPID! >nul 2>nul
    REM Give Windows a moment to actually free the socket before we rebind it.
    REM ping instead of timeout: timeout aborts with "input redirection is not
    REM supported" when start.bat is run from a redirected/non-interactive shell.
    ping -n 2 127.0.0.1 >nul 2>nul
    set "STILLTHERE="
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :17613 ^| findstr LISTENING 2^>nul') do (
        set "STILLTHERE=%%a"
    )
    if defined STILLTHERE (
        echo.
        echo   WARNING: port 17613 is still held by pid !STILLTHERE! after trying
        echo   to close the previous bridge. If the bridge below fails to start,
        echo   close that process manually in Task Manager ^(or restart Windows^)
        echo   and run start.bat again.
        echo.
        call :log "WARNING: port 17613 still held by pid !STILLTHERE! after taskkill."
    )
)

echo.
echo  ############################################################
echo  ##                                                        ##
echo  ##   El bridge se lanza OCULTO (pythonw.exe).             ##
echo  ##   Esta ventana de inicio puede cerrarse;               ##
echo  ##   el bridge y el mensajero siguen en segundo plano.    ##
echo  ##                                                        ##
echo  ############################################################
echo.
REM --- Chat local (carpeta chat-local): servidor oculto en http://127.0.0.1:8765 ---
call :start_chat

REM --- Despertar: verifica archivos; el bridge arranca el mensajero automaticamente ---
call :check_despertar

call :log "Launching bridge.py with %PYW% - hidden, detached"
REM pythonw.exe is a GUI-subsystem binary: it has no console at all, so this
REM starts the bridge completely windowless and returns immediately. No cmd /c
REM wrapper and no VBScript in between (both caused quote/stdin problems).
if not defined PYW goto :launch_console
start "" "%PYW%" "%~dp0bridge.py"
goto :launch_wait
:launch_console
call :log "pythonw.exe unavailable - launching the bridge in its own console"
start "ZeroScript Bridge" %PY% "%~dp0bridge.py"
:launch_wait
REM Wait ~3 s for it to bind the port, then report whether it answered.
ping -n 4 127.0.0.1 >nul 2>nul
set "BRIDGE_EXIT=0"
set "BRPORT="
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :17613 ^| findstr LISTENING 2^>nul') do set "BRPORT=%%a"
call :log "bridge.py launched hidden - listener pid !BRPORT!"

REM NO cerramos el chat local aqui: el bridge ya no vive en esta ventana, asi
REM que start.bat termina enseguida y el chat (http://127.0.0.1:8765) debe
REM seguir disponible. lanzar_chat.ps1 reutiliza el servidor en el proximo
REM arranque, y :stop_chat sigue existiendo para uso manual.

echo.
if defined BRPORT (
    echo   Bridge ACTIVO en ws://127.0.0.1:17613  ^(pid !BRPORT!^)
    echo   Mensajero y PC agent corriendo en segundo plano, sin ventanas.
    echo   Logs: logs\bridge_debug.log y logs\despertar.log
) else (
    echo   AVISO: el bridge no responde todavia en el puerto 17613.
    echo   Revisa logs\bridge_debug.log y logs\start.log
)
echo   Presiona una tecla para cerrar SOLO esta ventana de inicio.
pause >nul
exit /b 0

REM --- Subroutine: verify %PY% is a real, usable Python ------------------------
REM Returns 0 only if the interpreter runs, has a working pip, AND is Python 3.9
REM or newer. The pip check rejects the Microsoft Store stub (WindowsApps\
REM python.exe). The version check rejects old interpreters (e.g. 3.7/3.8) that
REM lack asyncio.to_thread, which the bridge requires.
:validate_py
REM Empty PY would turn the next lines into "-m ..." / "-c ..." and cmd would
REM print "'-m' is not recognized" before we even try. Bail out silently.
if not defined PY exit /b 1
%PY% -m pip --version >nul 2>nul || exit /b 1
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
exit /b %errorlevel%

REM --- Subroutine: append a line to start.log (best-effort, never blocks) -----
:log
REM Redirect FIRST, then echo. With the redirect at the end, a message that
REM ENDS IN A DIGIT (e.g. "exited with code 0") makes cmd parse "0>>" as a
REM file-handle redirect: the digit is eaten and the line prints to the console
REM instead of the log (seen live). echo( is the safe echo form for arbitrary text.
>>"%LOGFILE%" 2>nul echo(%~1
exit /b 0

REM --- Subroutine: start/verify the local chat and open it in the browser -------
REM lanzar_chat.ps1 waits until http://127.0.0.1:8765 answers and then opens the
REM browser exactly once. It also handles a chat server left from a previous
REM run. It is launched in the background so the bridge starts immediately.
:start_chat
if not exist "%~dp0chat-local\server.py" (
    call :log "Chat local: server.py not found; browser not opened."
    exit /b 0
)
if not exist "%~dp0chat-local\chat.html" (
    call :log "Chat local: chat.html not found; browser not opened."
    exit /b 0
)
if not exist "%~dp0chat-local\lanzar_chat.ps1" (
    call :log "Chat local: lanzar_chat.ps1 not found; browser not opened."
    exit /b 0
)
set "PYEXE="
for /f "delims=" %%P in ('call %PY% -c "import sys;print(sys.executable)" 2^>nul') do set "PYEXE=%%P"
if not defined PYEXE (
    call :log "Chat local: could not resolve the Python executable; browser not opened."
    exit /b 0
)
start "" /b powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0chat-local\lanzar_chat.ps1" -PythonExe "!PYEXE!" -Port 8765 >nul 2>nul
echo         Chat local: comprobando http://127.0.0.1:8765
call :log "Chat local: launcher started with '!PYEXE!' on port 8765; browser opens when it responds."
exit /b 0

REM --- Subroutine: despertar (archivos y comandos manuales) --------------------
REM El bridge arranca el mensajero del buzon por su cuenta (wake_watch). Aqui
REM solo se comprueba que existan los archivos y se muestran los comandos
REM manuales de despertar.bat.
:check_despertar
if not exist "%~dp0despertar.bat" (
    call :log "Despertar: despertar.bat not found."
    exit /b 0
)
if not exist "%~dp0despertar.py" (
    call :log "Despertar: despertar.py not found."
    exit /b 0
)
echo.
echo         Mensajero listo ^(el bridge lo arranca automaticamente^):
echo           despertar.bat /opencode   - OpenCode (automatico)
echo           despertar.bat /claude     - Claude (solo estado; no se despierta)
echo           solo despierta si el mensaje lleva @despertar o [despertar]
echo           ^(agrega /simular para probar sin activar; crea wake_off para apagarlo^)
if exist "%~dp0wake_off" echo         AVISO: existe wake_off, el mensajero esta apagado.
call :log "Despertar: OpenCode automatic; Claude manual; token @despertar."
exit /b 0

REM --- Subroutine: stop the local chat server started above -------------------
REM lanzar_chat.ps1 only stops the process if its command line matches
REM chat-local\server.py, so a different program on port 8765 is left alone.
:stop_chat
if not exist "%~dp0chat-local\lanzar_chat.ps1" exit /b 0
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0chat-local\lanzar_chat.ps1" -Stop -Port 8765 >nul 2>nul
call :log "Chat local: stop requested - port 8765 - exit !errorlevel!"
exit /b 0
