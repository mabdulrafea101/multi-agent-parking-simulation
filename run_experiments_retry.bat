@echo off
REM run_experiments_retry.bat — Run the full 480-experiment suite with timestamped backups (CMD)
REM Usage: run_experiments_retry.bat [replications]
setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM --- Default replication count from first arg ---
set "REPS=30"
if not "%~1"=="" set "REPS=%~1"

REM --- Environment setup ---
if not defined SUMO_HOME (
    if exist "C:\Program Files (x86)\Eclipse SUMO" (
        set "SUMO_HOME=C:\Program Files (x86)\Eclipse SUMO"
    ) else if exist "C:\Program Files\Eclipse SUMO" (
        set "SUMO_HOME=C:\Program Files\Eclipse SUMO"
    ) else if exist "C:\SUMO" (
        set "SUMO_HOME=C:\SUMO"
    )
)
if defined SUMO_HOME set "PATH=%SUMO_HOME%\bin;%PATH%"
set "PYTHONUNBUFFERED=1"

echo === 480-Experiment Suite ===
echo Replications: %REPS%
echo SUMO_HOME: %SUMO_HOME%

REM --- Ensure output dirs exist ---
if not exist "output\csv"   mkdir "output\csv"
if not exist "output\figures" mkdir "output\figures"
if not exist "output\tables"  mkdir "output\tables"
if not exist "output\sumo"  mkdir "output\sumo"

REM --- Backup old results with POSIX-style timestamp (via PowerShell) ---
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "[int][double]::Parse((Get-Date -UFormat %%s))"`) do set "TS=%%T"

if exist "output\csv\experiment_results.csv" move /y "output\csv\experiment_results.csv" "output\csv\experiment_results.csv.bak.%TS%" >nul
if exist "output\csv\summary_statistics.csv" move /y "output\csv\summary_statistics.csv" "output\csv\summary_statistics.csv.bak.%TS%" >nul
if exist "output\csv\por_timeseries.csv"     move /y "output\csv\por_timeseries.csv"     "output\csv\por_timeseries.csv.bak.%TS%"     >nul

REM --- Kill stale SUMO ---
taskkill /F /IM sumo.exe 2>nul
taskkill /F /IM sumo-gui.exe 2>nul
ping -n 3 127.0.0.1 >nul

REM --- Run ---
venv\Scripts\python.exe experiments.py --all-scenarios --replications %REPS% > output\experiment_run.log 2>&1

echo.
echo === Results ===
if exist "output\csv\experiment_results.csv" (
    set "TOTAL=0"
    for /f "usebackq delims=" %%L in ("output\csv\experiment_results.csv") do set /a "TOTAL+=1"
    set /a "DATA=TOTAL-1"
    echo   experiment_results.csv: !TOTAL! lines ^(!DATA! data rows^)
) else (
    echo   MISSING
)
