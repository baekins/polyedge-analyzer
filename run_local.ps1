# PolyEdge Analyzer – Developer local run (with venv)
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $ScriptDir

# Create venv if needed
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Green
    python -m venv .venv
}

# Activate
& .venv\Scripts\Activate.ps1

# Install deps
Write-Host "Installing dependencies..." -ForegroundColor Green
pip install -e ".[dev]" --quiet

# Run
Write-Host "Launching PolyEdge Analyzer..." -ForegroundColor Cyan
python -m app.main

Pop-Location
