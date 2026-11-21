@echo off
setlocal EnableDelayedExpansion

rem ZeroScript PC agent launcher for MCP clients and manual testing.
rem stdout must only carry JSON-RPC messages, so every diagnostic goes to stderr.
rem This wrapper also logs every invocation (timestamp, args, python, exit code) to a daily log file.

set "SCRIPT=%~dp0pc_agent_mcp.py"
set "PYTHON_CMD="
set "LOG_DIR=%~dp0logs"

rem Get consistent timestamp for log filename (YYYYMMDD) - fallback if wmic is absent (Win11 24H2+)
set "LOG_DATE="
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value 2^>nul') do set "LOG_DATE=%%I"
if defined LOG_DATE (
  set "TS=!LOG_DATE:~0,4!-!LOG_DATE:~4,2!-!LOG_DATE:~6,2! !LOG_DATE:~8,2!:!LOG_DATE:~10,2!:!LOG_DATE:~12,2!"
  set "LOG_DATE=!LOG_DATE:~0,4!!LOG_DATE:~4,2!!LOG_DATE:~6,2!"
) else (
  for /f "tokens=1,2 delims=|" %%A in ('powershell -NoProfile -Command "Get-Date -Format 'yyyyMMdd|yyyy-MM-dd HH:mm:ss'" 2^>nul') do (
    set "LOG_DATE=%%A"
    set "TS=%%B"
  )
)
if not defined LOG_DATE set "LOG_DATE=unknown"
if not defined TS set "TS=%DATE% %TIME%"
set "LOG_FILE=%LOG_DIR%\pc_agent_mcp_%LOG_DATE%.log"

rem Ensure log directory exists
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>nul
if not exist "%LOG_DIR%" (
  rem Fallback: try with explicit quoted path
  mkdir "%~dp0logs" >nul 2>nul
)

rem Log the start of this invocation (to stderr so stdout stays clean for JSON-RPC)
echo [pc-agent] !TS! INVOCATION args=%* cwd=%~dp0 python=resolving... 1>&2
echo !TS! ^| INVOCATION ^| args=%* ^| cwd=%~dp0 ^| python=resolving... >> "%LOG_FILE%" 2>nul

rem Find Python 3.9+ (1: bundled portable runtime if writable, 2: py launcher, 3: python on PATH, 4: standard dirs)
if exist "%~dp0runtime\python\python.exe" (
  "%~dp0runtime\python\python.exe" -c "import pathlib,sys; p=pathlib.Path(sys.argv[1]); p.write_text('ok'); p.unlink(); raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" "%LOG_DIR%\.py_write_test" >nul 2>nul
  if not errorlevel 1 set PYTHON_CMD="%~dp0runtime\python\python.exe"
)

if not defined PYTHON_CMD (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py -3"
  )
)

if not defined PYTHON_CMD (
  where python >nul 2>nul
  if not errorlevel 1 (
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
  )
)

if not defined PYTHON_CMD (
  for %%R in ("%LOCALAPPDATA%\Programs\Python" "%ProgramFiles%" "%ProgramFiles(x86)%") do (
    if not defined PYTHON_CMD if exist "%%~R" (
      for /f "delims=" %%D in ('dir /b /ad /o-n "%%~R\Python3*" 2^>nul') do (
        if not defined PYTHON_CMD if exist "%%~R\%%D\python.exe" (
          "%%~R\%%D\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
          if not errorlevel 1 set PYTHON_CMD="%%~R\%%D\python.exe"
        )
      )
    )
  )
)

if not defined PYTHON_CMD (
  echo [pc-agent] Python 3.9+ was not found. Run preparar_portable.bat or install Python 3.9+. 1>&2
  echo !TS! ^| ERROR ^| Python 3.9+ not found >> "%LOG_FILE%" 2>nul
  exit /b 9009
)

rem Log which python we're using
for /f "tokens=*" %%A in ('call %PYTHON_CMD% -c "import sys; print(sys.executable)" 2^>nul') do set "PY_EXE=%%A"
echo [pc-agent] Using Python: %PY_EXE% 1>&2
echo !TS! ^| PYTHON ^| %PY_EXE% >> "%LOG_FILE%" 2>nul

rem Run the actual agent, capture exit code
call %PYTHON_CMD% "%SCRIPT%" %*
set "EXIT_CODE=%ERRORLEVEL%"

rem Log completion with exit code
set "TS_END="
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value 2^>nul') do set "TS_END=%%I"
if defined TS_END (
  set "TS_END=!TS_END:~0,4!-!TS_END:~4,2!-!TS_END:~6,2! !TS_END:~8,2!:!TS_END:~10,2!:!TS_END:~12,2!"
) else (
  set "TS_END=%DATE% %TIME%"
)
echo [pc-agent] !TS_END! EXIT code=%EXIT_CODE% 1>&2
echo !TS_END! ^| EXIT ^| code=%EXIT_CODE% >> "%LOG_FILE%" 2>nul

exit /b %EXIT_CODE%