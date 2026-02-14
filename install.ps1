# PolyEdge Analyzer – One-line Windows Installer
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/baekins/polyedge-analyzer/main/install.ps1 | iex"

$ErrorActionPreference = "Stop"

$AppName    = "PolyEdgeAnalyzer"
$RepoOwner  = "baekins"
$RepoName   = "polyedge-analyzer"
$InstallDir = Join-Path $env:LOCALAPPDATA $AppName
$ExeName    = "PolyEdgeAnalyzer.exe"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║        PolyEdge Analyzer – Installer                     ║" -ForegroundColor Cyan
Write-Host "║  ⚠️  This tool does NOT guarantee profits.               ║" -ForegroundColor Yellow
Write-Host "║  You may lose money. Use responsibly.                    ║" -ForegroundColor Yellow
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# 1. Determine latest release
Write-Host "[1/4] Finding latest release..." -ForegroundColor Green
$apiUrl  = "https://api.github.com/repos/$RepoOwner/$RepoName/releases/latest"
try {
    $release = Invoke-RestMethod -Uri $apiUrl -Headers @{ "User-Agent" = "PolyEdgeInstaller" }
} catch {
    Write-Host "ERROR: Could not fetch latest release. Check your internet connection." -ForegroundColor Red
    Write-Host "       URL: $apiUrl" -ForegroundColor Gray
    exit 1
}

$asset = $release.assets | Where-Object { $_.name -like "*.exe" } | Select-Object -First 1
if (-not $asset) {
    Write-Host "ERROR: No .exe asset found in release $($release.tag_name)." -ForegroundColor Red
    exit 1
}

$downloadUrl = $asset.browser_download_url
$version     = $release.tag_name
Write-Host "       Found version $version" -ForegroundColor Gray

# 2. Download
Write-Host "[2/4] Downloading $($asset.name) ($([math]::Round($asset.size / 1MB, 1)) MB)..." -ForegroundColor Green
if (-not (Test-Path $InstallDir)) { New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null }
$exePath = Join-Path $InstallDir $ExeName

try {
    # Use BITS for progress bar; fallback to Invoke-WebRequest
    Start-BitsTransfer -Source $downloadUrl -Destination $exePath -Description "Downloading PolyEdge Analyzer"
} catch {
    Invoke-WebRequest -Uri $downloadUrl -OutFile $exePath -UseBasicParsing
}

# 3. Create desktop shortcut
Write-Host "[3/4] Creating desktop shortcut..." -ForegroundColor Green
$desktop    = [Environment]::GetFolderPath("Desktop")
$lnkPath    = Join-Path $desktop "$AppName.lnk"
$wshShell   = New-Object -ComObject WScript.Shell
$shortcut   = $wshShell.CreateShortcut($lnkPath)
$shortcut.TargetPath       = $exePath
$shortcut.WorkingDirectory = $InstallDir
$shortcut.Description      = "PolyEdge Analyzer – Polymarket Sports EV Scanner"
$shortcut.Save()

# 4. (Optional) Start Menu shortcut
$startMenu = Join-Path ([Environment]::GetFolderPath("Programs")) $AppName
if (-not (Test-Path $startMenu)) { New-Item -ItemType Directory -Path $startMenu -Force | Out-Null }
$startLnk  = Join-Path $startMenu "$AppName.lnk"
$shortcut2  = $wshShell.CreateShortcut($startLnk)
$shortcut2.TargetPath       = $exePath
$shortcut2.WorkingDirectory = $InstallDir
$shortcut2.Description      = "PolyEdge Analyzer"
$shortcut2.Save()

Write-Host "[4/4] Done!" -ForegroundColor Green
Write-Host ""
Write-Host "  Installed to: $InstallDir" -ForegroundColor Gray
Write-Host "  Desktop shortcut created." -ForegroundColor Gray
Write-Host ""
Write-Host "  ⚠️  Windows SmartScreen may warn you on first run." -ForegroundColor Yellow
Write-Host "     Click 'More info' → 'Run anyway' to proceed." -ForegroundColor Yellow
Write-Host ""
Write-Host "  Double-click '$AppName' on your Desktop to launch!" -ForegroundColor Cyan
Write-Host ""
