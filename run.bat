@echo off
REM Launch zLog on Windows. Double-click this file or run it from a terminal.
REM Requires uv (https://docs.astral.sh/uv/) and, for live logs, adb on PATH.

REM Work from this script's folder so it runs no matter where it's launched.
cd /d "%~dp0"

REM Make sure uv is available.
where uv >nul 2>nul
if errorlevel 1 (
    echo.
    echo [zLog] 'uv' was not found on your PATH.
    echo        Install it from: https://docs.astral.sh/uv/getting-started/installation/
    echo.
    pause
    exit /b 1
)

echo [zLog] Starting... (uv will set up the environment on first run)
echo.

REM uv run creates/syncs the virtualenv from uv.lock, then launches the app.
REM Any arguments passed to run.bat are forwarded to zlog.
uv run zlog %*
set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
    echo.
    echo [zLog] Exited with error code %EXITCODE%. See the messages above.
    echo        Tip: run 'adb devices' in a terminal to confirm your device is connected.
    echo.
    pause
)

exit /b %EXITCODE%
