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

# SUMO configuration (optional — simulation falls back to Mesa-only if absent).
# Ask the same resolver the simulation uses, so this banner can never disagree
# with what the app actually finds (pip wheel, Homebrew, apt or MSI install).
if (-not $env:SUMO_HOME) {
    $probe = "from engine.sumo_integration import _default_sumo_home; print(_default_sumo_home())"
    $probed = & venv\Scripts\python.exe -c $probe 2>$null
    if ($probed) { $env:SUMO_HOME = "$probed".Trim() }
}
if ($env:SUMO_HOME) {
    $env:PATH = "$env:SUMO_HOME\bin;$env:PATH"
    Write-Host "[run_dashboard] SUMO_HOME=$env:SUMO_HOME"
} else {
    Write-Host "[run_dashboard] SUMO not found - running in Mesa-only mode"
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
