@echo off
REM Run zLog's checks: unit tests, lint, and format check.
REM Double-click this file or run it from a terminal. Requires uv.

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

echo [zLog] Installing dev dependencies (first run may take a moment)...
uv sync --extra dev
if errorlevel 1 goto :failed

echo.
echo [zLog] Running tests...
uv run pytest -q
if errorlevel 1 goto :failed

echo.
echo [zLog] Linting...
uv run ruff check .
if errorlevel 1 goto :failed

echo.
echo [zLog] Checking formatting...
uv run ruff format --check .
if errorlevel 1 goto :failed

echo.
echo [zLog] All checks passed.
pause
exit /b 0

:failed
echo.
echo [zLog] Checks failed. See the messages above.
pause
exit /b 1
