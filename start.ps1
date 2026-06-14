# SRT Flow - Start Frontend & Backend
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SRT Flow - Starting Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Read PORT from .env
$Port = "8081"
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^PORT=(.+)$") { $Port = $Matches[1].Trim() }
    }
}

# Start backend in new window
Write-Host "[1/2] Starting backend (port $Port)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
Set-Location '$ProjectRoot'
& '.\venv\Scripts\Activate.ps1'
uvicorn backend.app.main:app --host 0.0.0.0 --port $Port --log-level info
"@

Start-Sleep -Seconds 2

# Start frontend in new window
Write-Host "[2/2] Starting frontend..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
Set-Location '$ProjectRoot\frontend'
npm run dev
"@

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Backend:  http://localhost:$Port" -ForegroundColor Yellow
Write-Host "  Frontend: http://localhost:3000" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
