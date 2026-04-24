@echo off
setlocal

:: ── fabric-drawio runner ──────────────────────────────────────────────────────

where uv >nul 2>&1
if errorlevel 1 (
    echo ERROR: uv is not installed or not on PATH.
    echo Install it from https://docs.astral.sh/uv/getting-started/installation/
    exit /b 1
)

if not exist ".env" (
    if not exist ".env.example" goto :menu
    echo WARNING: .env not found. Copy .env.example to .env and fill in your credentials.
    echo          Continuing -- values may already be set in the environment.
    echo.
)

:menu
echo ============================================================
echo   fabric-drawio -- Medallion Architecture Diagram Generator
echo ============================================================
echo.
echo   1. Demo mode     (example data, no Azure credentials needed)
echo   2. Active epics  (live Azure DevOps + Purview APIs)
echo.
set /p CHOICE="Select [1/2]: "

if "%CHOICE%"=="1" goto :demo
if "%CHOICE%"=="2" goto :active

echo Invalid choice. Please enter 1 or 2.
echo.
goto :menu

:demo
echo.
uv run python -m agent.main --demo
goto :end

:active
echo.
uv run python -m agent.main --state Active
goto :end

:end
endlocal
