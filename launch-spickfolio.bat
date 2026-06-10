@echo off
setlocal
cd /d "%~dp0"

if /I "%~1"=="--stop" (
    python -m spick_folio.launcher --stop
    exit /b %ERRORLEVEL%
)

if /I "%~1"=="--server-only" (
    python server.py
    exit /b %ERRORLEVEL%
)

python -m spick_folio.launcher %*
exit /b %ERRORLEVEL%
