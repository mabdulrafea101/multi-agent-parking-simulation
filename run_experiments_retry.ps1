# run_experiments_retry.ps1 — Run the full 480-experiment suite
[CmdletBinding()]
param(
    [int]$Replications = 30
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

Write-Host "=== 480-Experiment Suite ==="
Write-Host "Start: $(Get-Date)"
Write-Host "SUMO_HOME: $($env:SUMO_HOME)"

# --- Ensure output dirs exist ---
New-Item -ItemType Directory -Force -Path output\csv | Out-Null
New-Item -ItemType Directory -Force -Path output\figures | Out-Null
New-Item -ItemType Directory -Force -Path output\tables | Out-Null
New-Item -ItemType Directory -Force -Path output\sumo | Out-Null

# --- Backup old results (timestamped like the original) ---
$timestamp = [int][double]::Parse((Get-Date -UFormat %s))
$backupFiles = @("experiment_results.csv", "summary_statistics.csv", "por_timeseries.csv")
foreach ($f in $backupFiles) {
    $src = "output\csv\$f"
    if (Test-Path $src) {
        $dst = "output\csv\${f}.bak.${timestamp}"
        Move-Item -Path $src -Destination $dst -Force
    }
}

# --- Kill stale SUMO ---
foreach ($proc in @("sumo", "sumo-gui")) {
    Get-Process -Name "$proc.exe" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2

# --- Run ---
& .\venv\Scripts\python.exe experiments.py --all-scenarios --replications $Replications 2>&1 | Tee-Object -FilePath "output\experiment_run.log"

Write-Host ""
Write-Host "=== Finished: $(Get-Date) ==="
Write-Host "Results:"
$resultsPath = "output\csv\experiment_results.csv"
if (Test-Path $resultsPath) {
    $lines = Get-Content $resultsPath
    Write-Host "  experiment_results.csv: $($lines.Count) lines"
} else {
    Write-Host "  MISSING"
}
