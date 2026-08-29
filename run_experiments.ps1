# run_experiments.ps1 — Run the full 480-experiment suite with proper env setup
[CmdletBinding()]
param(
    [int]$Replications = 30
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# --- Environment setup ---
# Probe common SUMO install paths if SUMO_HOME is not already set
if (-not $env:SUMO_HOME) {
    $sumoCandidates = @(
        "C:\Program Files (x86)\Eclipse SUMO",
        "C:\Program Files\Eclipse SUMO",
        "C:\SUMO"
    )
    foreach ($p in $sumoCandidates) {
        if (Test-Path $p) {
            $env:SUMO_HOME = $p
            break
        }
    }
}
if ($env:SUMO_HOME) {
    $env:PATH = "$env:SUMO_HOME\bin;$env:PATH"
}
$env:PYTHONUNBUFFERED = "1"

Write-Host "============================================"
Write-Host "  Running 480-Experiment Suite"
Write-Host "  SUMO_HOME: $($env:SUMO_HOME)"
Write-Host "  Replications: $Replications"
Write-Host "  Start: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "============================================"

# --- Ensure output dirs exist ---
New-Item -ItemType Directory -Force -Path output\csv | Out-Null
New-Item -ItemType Directory -Force -Path output\figures | Out-Null
New-Item -ItemType Directory -Force -Path output\tables | Out-Null
New-Item -ItemType Directory -Force -Path output\sumo | Out-Null

# --- Back up previous run outputs (v1_mesamostly naming preserved) ---
$backupFiles = @("experiment_results.csv", "summary_statistics.csv", "por_timeseries.csv")
foreach ($f in $backupFiles) {
    $src = "output\csv\$f"
    if (Test-Path $src) {
        $dst = "output\csv\$($f -replace '\.csv$', '_v1_mesamostly.csv')"
        Move-Item -Path $src -Destination $dst -Force
    }
}

# --- Kill any stale SUMO processes ---
foreach ($proc in @("sumo", "sumo-gui")) {
    Get-Process -Name "$proc.exe" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2

# --- Run experiments ---
& .\venv\Scripts\python.exe experiments.py --all-scenarios --replications $Replications 2>&1 | Tee-Object -FilePath "output\experiment_run.log"
$exitCode = $LASTEXITCODE

Write-Host ""
Write-Host "============================================"
Write-Host "  Experiment suite finished"
Write-Host "  Exit code: $exitCode"
Write-Host "  End: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "============================================"

# --- Verify output ---
Write-Host ""
Write-Host "Output files:"
foreach ($f in $backupFiles) {
    $p = "output\csv\$f"
    if (Test-Path $p) {
        $info = Get-Item $p
        Write-Host "  OK   $p ($($info.Length) bytes)"
    } else {
        Write-Host "  MISSING: $p"
    }
}

# --- Count rows ---
$resultsPath = "output\csv\experiment_results.csv"
if (Test-Path $resultsPath) {
    $lines = Get-Content $resultsPath
    $trueCount = ($lines | Where-Object { $_ -match ",True" }).Count
    Write-Host "  experiment_results.csv: $($lines.Count) lines (including header)"
    Write-Host "  sumo_connected=True: $trueCount rows"
}

exit $exitCode
