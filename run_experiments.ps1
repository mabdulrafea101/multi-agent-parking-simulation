# run_experiments.ps1 — Run the full 480-experiment suite with proper env setup
[CmdletBinding()]
param(
    [int]$Replications = 30,
    [ValidateSet("mesa", "sumo", "osm_city")]
    [string]$SimulationType = "auto",
    [string]$City
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# --- Environment setup ---
# Ask the same resolver the simulation uses, so this echo can never disagree
# with what the app actually finds (pip wheel, Homebrew, apt or MSI install).
if (-not $env:SUMO_HOME) {
    $probe = "from engine.sumo_integration import _default_sumo_home; print(_default_sumo_home())"
    $probed = & .\venv\Scripts\python.exe -c $probe 2>$null
    if ($probed) { $env:SUMO_HOME = "$probed".Trim() }
}
if ($env:SUMO_HOME) {
    $env:PATH = "$env:SUMO_HOME\bin;$env:PATH"
}
$env:PYTHONUNBUFFERED = "1"

Write-Host "============================================"
Write-Host "  Running 480-Experiment Suite"
Write-Host "  SUMO_HOME: $($env:SUMO_HOME)"
Write-Host "  Replications: $Replications"
Write-Host "  SimulationType: $SimulationType (auto = SUMO if available, else mesa)"
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
$expArgs = @("--all-scenarios", "--replications", $Replications)
if ($SimulationType -ne "auto") {
    $expArgs += @("--simulation-type", $SimulationType)
    if ($SimulationType -eq "osm_city" -and $City) {
        $expArgs += @("--city", $City)
    }
} else {
    # Auto-pick SUMO when installed (eclipse-sumo pip wheel or system install).
    $sumoProbe = & .\venv\Scripts\python.exe -c "from engine.sumo_integration import _sumo_bin; import os; print('OK' if os.path.isfile(_sumo_bin('sumo')) and os.path.isfile(_sumo_bin('netgenerate')) else 'NO')" 2>$null
    if ($sumoProbe -eq "OK") {
        $expArgs += @("--simulation-type", "sumo")
        Write-Host "[run_experiments] Auto-selected simulation-type: sumo (SUMO detected)"
    } else {
        Write-Host "[run_experiments] SUMO not detected - running Mesa-only"
    }
}
& .\venv\Scripts\python.exe experiments.py @expArgs 2>&1 | Tee-Object -FilePath "output\experiment_run.log"
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
