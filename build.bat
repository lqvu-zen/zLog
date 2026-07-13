@echo off
REM Build the zLog Windows executable with cx_Freeze.
REM Double-click or run from a terminal. Requires uv.

cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
    echo.
    echo [zLog] 'uv' was not found on your PATH.
    echo        Install it from: https://docs.astral.sh/uv/getting-started/installation/
    echo.
    pause
    exit /b 1
)

echo [zLog] Building the executable with cx_Freeze...
echo.
uv run --extra build python cxfreeze_setup.py build
set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
    echo.
    echo [zLog] Build failed with code %EXITCODE%. See the messages above.
    echo.
    pause
    exit /b %EXITCODE%
)

echo.
echo [zLog] Done. Find zlog.exe under the build\ folder (build\exe.win-amd64-*\).
pause
exit /b 0
