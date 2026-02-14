# PolyEdge Analyzer – Uninstaller
$ErrorActionPreference = "Stop"

$AppName    = "PolyEdgeAnalyzer"
$InstallDir = Join-Path $env:LOCALAPPDATA $AppName

Write-Host "Uninstalling PolyEdge Analyzer..." -ForegroundColor Yellow

# Remove desktop shortcut
$desktop = [Environment]::GetFolderPath("Desktop")
$lnk = Join-Path $desktop "$AppName.lnk"
if (Test-Path $lnk) { Remove-Item $lnk -Force; Write-Host "  Removed desktop shortcut." }

# Remove start menu shortcut
$startMenu = Join-Path ([Environment]::GetFolderPath("Programs")) $AppName
if (Test-Path $startMenu) { Remove-Item $startMenu -Recurse -Force; Write-Host "  Removed start menu entry." }

# Remove install directory
if (Test-Path $InstallDir) { Remove-Item $InstallDir -Recurse -Force; Write-Host "  Removed $InstallDir." }

Write-Host "Uninstall complete." -ForegroundColor Green
Write-Host "Note: settings in %LOCALAPPDATA%\PolyEdgeAnalyzer were also removed." -ForegroundColor Gray
