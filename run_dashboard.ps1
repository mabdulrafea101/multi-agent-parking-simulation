# run_dashboard.ps1 — Launch the Multi-Agent Parking Simulation Web Dashboard
# Usage: .\run_dashboard.ps1 [-Port 5000] [-Debug]
[CmdletBinding()]
param(
    [int]$Port = 5000,
    [switch]$NoDebug
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# --- Environment setup ---
$env:FLASK_APP = "app:create_app"
$env:FLASK_ENV = "development"
$env:PYTHONUNBUFFERED = "1"

# SUMO configuration (optional — simulation falls back to Mesa-only if absent)
if (-not $env:SUMO_HOME) {
    $sumoCandidates = @(
        "C:\Program Files (x86)\Eclipse SUMO",
        "C:\Program Files\Eclipse SUMO",
        "C:\SUMO"
    )
    foreach ($p in $sumoCandidates) {
        if (Test-Path $p) {
            $env:SUMO_HOME = $p
            $env:PATH = "$p\bin;$env:PATH"
            Write-Host "[run_dashboard] SUMO_HOME=$p"
            break
        }
    }
    if (-not $env:SUMO_HOME) {
        Write-Host "[run_dashboard] SUMO not found - running in Mesa-only mode"
    }
}

# --- Ensure outputs exist ---
New-Item -ItemType Directory -Force -Path output\csv | Out-Null
New-Item -ItemType Directory -Force -Path output\figures | Out-Null
New-Item -ItemType Directory -Force -Path output\tables | Out-Null

# --- Launch ---
$debugFlag = ""
if (-not $NoDebug) { $debugFlag = "--debug" }

Write-Host "============================================"
Write-Host "  Multi-Agent Parking Simulation Dashboard"
Write-Host "============================================"
Write-Host "  URL:    http://localhost:${Port}"
Write-Host "  Debug:  $(if ($NoDebug) { 'off' } else { 'on' })"
Write-Host "  SUMO:   $(if ($env:SUMO_HOME) { $env:SUMO_HOME } else { 'not found (Mesa-only)' })"
Write-Host "============================================"

& venv\Scripts\python.exe -m flask --app app:create_app run --host=127.0.0.1 --port=$Port $debugFlag
