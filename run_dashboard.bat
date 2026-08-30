@echo off
REM run_dashboard.bat — Launch the Multi-Agent Parking Simulation Web Dashboard (CMD)
REM Usage: run_dashboard.bat [--port 5000] [--no-debug]
setlocal

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM --- Environment setup ---
set "FLASK_APP=app:create_app"
set "FLASK_ENV=development"
set "PYTHONUNBUFFERED=1"

REM --- SUMO configuration (optional) ---
REM Ask the same resolver the simulation uses, so this banner can never disagree
REM with what the app actually finds (pip wheel, Homebrew, apt or MSI install).
if defined SUMO_HOME goto sumo_ready
for /f "usebackq delims=" %%i in (`venv\Scripts\python.exe -c "from engine.sumo_integration import _default_sumo_home; print(_default_sumo_home())" 2^>nul`) do set "SUMO_HOME=%%i"
:sumo_ready
if defined SUMO_HOME (
    set "PATH=%SUMO_HOME%\bin;%PATH%"
    echo [run_dashboard] SUMO_HOME=%SUMO_HOME%
) else (
    echo [run_dashboard] SUMO not found - running in Mesa-only mode
)

REM --- Ensure outputs exist ---
if not exist "output\csv"   mkdir "output\csv"
if not exist "output\figures" mkdir "output\figures"
if not exist "output\tables"  mkdir "output\tables"

REM --- Parse args ---
set "PORT=5000"
set "DEBUG=--debug"
:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="--no-debug" (
    set "DEBUG="
    shift
    goto parse_args
)
if /i "%~1"=="--debug" (
    set "DEBUG=--debug"
    shift
    goto parse_args
)
if /i "%~1"=="--port" (
    if not "%~2"=="" set "PORT=%~2"
    shift
    shift
    goto parse_args
)
echo Unknown arg: %~1
exit /b 1
:args_done

echo ============================================
echo   Multi-Agent Parking Simulation Dashboard
echo ============================================
echo   URL:    http://localhost:%PORT%
if defined DEBUG (
    echo   Debug:  on
) else (
    echo   Debug:  off
)
if defined SUMO_HOME (
    echo   SUMO:   %SUMO_HOME%
) else (
    echo   SUMO:   not found (Mesa-only^)
)
echo ============================================

venv\Scripts\python.exe -m flask --app app:create_app run --host=127.0.0.1 --port=%PORT% %DEBUG%
