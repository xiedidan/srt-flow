# SRT Flow - Stop Frontend & Backend
$ErrorActionPreference = "SilentlyContinue"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SRT Flow - Stopping Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Read PORT from .env
$Port = "8081"
if (Test-Path "$ProjectRoot\.env") {
    Get-Content "$ProjectRoot\.env" | ForEach-Object {
        if ($_ -match "^PORT=(.+)$") { $Port = $Matches[1].Trim() }
    }
}

# Helper: kill all processes on a given port (any TCP state)
function Stop-Port {
    param([string]$PortNum, [string]$Label)
    $pids = Get-NetTCPConnection -LocalPort $PortNum -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    $killed = $false
    foreach ($p in $pids) {
        $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "  Killing process: $($proc.Name) (PID $p)" -ForegroundColor Yellow
            Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
            $killed = $true
        }
    }
    if ($killed) {
        Write-Host "  $Label stopped." -ForegroundColor Green
    } else {
        Write-Host "  No process found on port $PortNum." -ForegroundColor DarkGray
    }
}

# Stop backend (uvicorn) - by port first, then by process name as fallback
Write-Host "[1/2] Stopping backend (port $Port)..." -ForegroundColor Green
Stop-Port -PortNum $Port -Label "Backend"
# Fallback: kill any leftover uvicorn processes
$uvicornProcs = Get-Process -Name "uvicorn" -ErrorAction SilentlyContinue
if ($uvicornProcs) {
    foreach ($proc in $uvicornProcs) {
        Write-Host "  Killing leftover uvicorn (PID $($proc.Id))" -ForegroundColor Yellow
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
}
# Also kill python processes running uvicorn
Get-WmiObject Win32_Process -Filter "Name='python.exe' OR Name='python3.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.CommandLine -match "uvicorn") {
        Write-Host "  Killing python uvicorn (PID $($_.ProcessId))" -ForegroundColor Yellow
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

# Stop frontend (Vite / node dev server) - by port first, then by process name as fallback
$FrontendPort = "3000"
Write-Host "[2/2] Stopping frontend (port $FrontendPort)..." -ForegroundColor Green
Stop-Port -PortNum $FrontendPort -Label "Frontend"
# Fallback: kill node processes running vite
Get-WmiObject Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.CommandLine -match "vite") {
        Write-Host "  Killing node vite (PID $($_.ProcessId))" -ForegroundColor Yellow
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  All services stopped." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""