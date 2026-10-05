# ReelForge One-Command Setup Script for Windows PowerShell
# Verifies toolchain, initializes Python virtual environment, installs Node/Remotion, downloads models.

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "         ReelForge Automated Environment Setup            " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check Python
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "[ERROR] Python 3.11+ is not installed or not in PATH." -ForegroundColor Red
    Exit 1
}
Write-Host "[OK] Found Python: $($pythonCmd.Source)" -ForegroundColor Green

# 2. Virtual Environment
if (-not (Test-Path ".venv")) {
    Write-Host "[*] Creating Python virtual environment in .venv..." -ForegroundColor Yellow
    python -m venv .venv
}
Write-Host "[OK] Python virtual environment ready." -ForegroundColor Green

# 3. Install Python Dependencies
Write-Host "[*] Installing Python dependencies via pip..." -ForegroundColor Yellow
.\.venv\Scripts\pip.exe install -e . --quiet
Write-Host "[OK] Python packages installed." -ForegroundColor Green

# 4. Check Node.js & Remotion
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCmd) {
    Write-Host "[ERROR] Node.js is required for Remotion video rendering." -ForegroundColor Red
    Exit 1
}
Write-Host "[OK] Found Node.js: $($nodeCmd.Source)" -ForegroundColor Green

if (Test-Path "render\package.json") {
    Write-Host "[*] Installing Remotion Node modules in render/..." -ForegroundColor Yellow
    Push-Location render
    npm install --quiet
    Pop-Location
    Write-Host "[OK] Remotion dependencies installed." -ForegroundColor Green
}

# 5. Check FFmpeg
$ffmpegCmd = Get-Command ffmpeg -ErrorAction SilentlyContinue
if (-not $ffmpegCmd) {
    Write-Host "[WARNING] ffmpeg not found in PATH. Install via winget install Gyan.FFmpeg" -ForegroundColor Yellow
} else {
    Write-Host "[OK] Found FFmpeg: $($ffmpegCmd.Source)" -ForegroundColor Green
}

# 6. Copy .env if not exists
if (-not (Test-Path ".env")) {
    Write-Host "[*] Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
}

# 7. Initialize SQLite DB
Write-Host "[*] Initializing SQLite database schema..." -ForegroundColor Yellow
.\.venv\Scripts\python.exe -c "from reelforge.db import init_db; init_db()"
Write-Host "[OK] Database initialized: reelforge.db" -ForegroundColor Green

# 8. Run Doctor
Write-Host "`n[*] Running ReelForge Doctor diagnostics..." -ForegroundColor Cyan
.\.venv\Scripts\python.exe -m reelforge.cli doctor

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Setup complete! Start generating: reelforge run --n 1    " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
