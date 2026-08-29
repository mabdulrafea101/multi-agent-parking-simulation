# run_experiments_retry.ps1 — Run the full 480-experiment suite
[CmdletBinding()]
param(
    [int]$Replications = 30
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# --- Environment setup ---
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
