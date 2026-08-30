@echo off
REM run_experiments.bat — Run the full 480-experiment suite (CMD)
REM Usage: run_experiments.bat [replications]
setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM --- Default replication count from first arg ---
set "REPS=30"
if not "%~1"=="" set "REPS=%~1"

REM --- Environment setup ---
REM Ask the same resolver the simulation uses, so this echo can never disagree
REM with what the app actually finds (pip wheel, Homebrew, apt or MSI install).
if defined SUMO_HOME goto sumo_ready
for /f "usebackq delims=" %%i in (`venv\Scripts\python.exe -c "from engine.sumo_integration import _default_sumo_home; print(_default_sumo_home())" 2^>nul`) do set "SUMO_HOME=%%i"
:sumo_ready
if defined SUMO_HOME set "PATH=%SUMO_HOME%\bin;%PATH%"
set "PYTHONUNBUFFERED=1"

echo ============================================
echo   Running 480-Experiment Suite
echo   SUMO_HOME: %SUMO_HOME%
echo   Replications: %REPS%
echo ============================================

REM --- Ensure output dirs exist ---
if not exist "output\csv"   mkdir "output\csv"
if not exist "output\figures" mkdir "output\figures"
if not exist "output\tables"  mkdir "output\tables"
if not exist "output\sumo"  mkdir "output\sumo"

REM --- Back up previous run outputs (v1_mesamostly naming preserved) ---
if exist "output\csv\experiment_results.csv"  move /y "output\csv\experiment_results.csv"  "output\csv\experiment_results_v1_mesamostly.csv"  >nul
if exist "output\csv\summary_statistics.csv"  move /y "output\csv\summary_statistics.csv"  "output\csv\summary_statistics_v1_mesamostly.csv"  >nul
if exist "output\csv\por_timeseries.csv"      move /y "output\csv\por_timeseries.csv"      "output\csv\por_timeseries_v1_mesamostly.csv"      >nul

REM --- Kill any stale SUMO processes ---
taskkill /F /IM sumo.exe 2>nul
taskkill /F /IM sumo-gui.exe 2>nul
ping -n 3 127.0.0.1 >nul

REM --- Auto-pick SUMO if available ---
set "SIM_TYPE="
venv\Scripts\python.exe -c "from engine.sumo_integration import _sumo_bin; import os, sys; sys.exit(0 if os.path.isfile(_sumo_bin('sumo')) and os.path.isfile(_sumo_bin('netgenerate')) else 1)" 1>nul 2>nul
if not errorlevel 1 (
    set "SIM_TYPE=--simulation-type sumo"
    echo [run_experiments] Auto-selected simulation-type: sumo (SUMO detected^)
) else (
    echo [run_experiments] SUMO not detected - running Mesa-only
)

REM --- Run experiments and tee to log ---
venv\Scripts\python.exe experiments.py --all-scenarios --replications %REPS% %SIM_TYPE% > output\experiment_run.log 2>&1
set "EXITCODE=%ERRORLEVEL%"

echo.
echo ============================================
echo   Experiment suite finished
echo   Exit code: %EXITCODE%
echo ============================================

REM --- Verify output ---
echo.
echo Output files:
if exist "output\csv\experiment_results.csv" (
    echo   OK   output\csv\experiment_results.csv
) else (
    echo   MISSING: output\csv\experiment_results.csv
)
if exist "output\csv\summary_statistics.csv" (
    echo   OK   output\csv\summary_statistics.csv
) else (
    echo   MISSING: output\csv\summary_statistics.csv
)
if exist "output\csv\por_timeseries.csv" (
    echo   OK   output\csv\por_timeseries.csv
) else (
    echo   MISSING: output\csv\por_timeseries.csv
)

REM --- Count rows in results CSV ---
if exist "output\csv\experiment_results.csv" (
    set "TOTAL=0"
    set "TRUECOUNT=0"
    for /f "usebackq delims=" %%L in ("output\csv\experiment_results.csv") do (
        set /a "TOTAL+=1"
        echo "%%L" | findstr /C:",True" >nul
        if not errorlevel 1 set /a "TRUECOUNT+=1"
    )
    set /a "DATA=TOTAL-1"
    echo   experiment_results.csv: !DATA! data rows ^(!TOTAL! total incl. header^)
    echo   sumo_connected=True: !TRUECOUNT! rows
)

exit /b %EXITCODE%
