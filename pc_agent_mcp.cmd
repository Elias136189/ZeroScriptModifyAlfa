@echo off
setlocal EnableDelayedExpansion

rem ZeroScript PC agent launcher for MCP clients and manual testing.
rem stdout must only carry JSON-RPC messages, so every diagnostic goes to stderr.
rem This wrapper also logs every invocation (timestamp, args, python, exit code) to a daily log file.

set "SCRIPT=%~dp0pc_agent_mcp.py"
set "PYTHON_CMD="
set "LOG_DIR=%~dp0logs"

rem Get consistent timestamp for log filename (YYYYMMDD) using wmic
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value 2^>nul') do set "LOG_DATE=%%I"
set "LOG_DATE=!LOG_DATE:~0,4!!LOG_DATE:~4,2!!LOG_DATE:~6,2!"
set "LOG_FILE=%LOG_DIR%\pc_agent_mcp_%LOG_DATE%.log"

rem Ensure log directory exists
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>nul
if not exist "%LOG_DIR%" (
  rem Fallback: try with explicit quoted path
  mkdir "%~dp0logs" >nul 2>nul
)

rem Timestamp for this invocation (YYYY-MM-DD HH:MM:SS)
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value 2^>nul') do set "TS=%%I"
set "TS=!TS:~0,4!-!TS:~4,2!-!TS:~6,2! !TS:~8,2!:!TS:~10,2!:!TS:~12,2!"

rem Log the start of this invocation (to stderr so stdout stays clean for JSON-RPC)
echo [pc-agent] !TS! INVOCATION args=%* cwd=%~dp0 python=resolving... 1>&2
echo !TS! ^| INVOCATION ^| args=%* ^| cwd=%~dp0 ^| python=resolving... >> "%LOG_FILE%" 2>nul

rem Find Python 3.9+ (prefer py launcher, then python)
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
  where python >nul 2>nul
  if not errorlevel 1 (
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
  )
)

if not defined PYTHON_CMD (
  echo [pc-agent] Python 3.9 or newer was not found. Install it or edit pc_agent_mcp.cmd. 1>&2
  echo !TS! ^| ERROR ^| Python 3.9+ not found >> "%LOG_FILE%" 2>nul
  exit /b 9009
)

rem Log which python we're using
for /f "tokens=*" %%A in ('%PYTHON_CMD% -c "import sys; print(sys.executable)" 2^>nul') do set "PY_EXE=%%A"
echo [pc-agent] Using Python: %PY_EXE% 1>&2
echo !TS! ^| PYTHON ^| %PY_EXE% >> "%LOG_FILE%" 2>nul

rem Run the actual agent, capture exit code
%PYTHON_CMD% "%SCRIPT%" %*
set "EXIT_CODE=%ERRORLEVEL%"

rem Log completion with exit code
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value 2^>nul') do set "TS_END=%%I"
set "TS_END=!TS_END:~0,4!-!TS_END:~4,2!-!TS_END:~6,2! !TS_END:~8,2!:!TS_END:~10,2!:!TS_END:~12,2!"
echo [pc-agent] !TS_END! EXIT code=%EXIT_CODE% 1>&2
echo !TS_END! ^| EXIT ^| code=%EXIT_CODE% >> "%LOG_FILE%" 2>nul

exit /b %EXIT_CODE%