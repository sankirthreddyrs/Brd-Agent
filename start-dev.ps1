<#
.SYNOPSIS
    One-click local developer startup script for BRD Agent (PowerShell).
.DESCRIPTION
    Checks environment files, installs dependencies if missing, and runs both
    FastAPI backend (0.0.0.0:8000) and React frontend (0.0.0.0:5173) simultaneously.
#>

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
if (-not $ScriptDir) { $ScriptDir = Get-Location }
Set-Location $ScriptDir

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "               BRD Agent - One-Click Dev Setup                  " -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check and copy backend .env if missing
if (-not (Test-Path "backend\.env")) {
    if (Test-Path "backend\.env.example") {
        Write-Host "[1/4] Creating backend/.env from backend/.env.example..." -ForegroundColor Yellow
        Copy-Item "backend\.env.example" "backend\.env"
        Write-Host "       backend/.env created successfully." -ForegroundColor Green
    } else {
        Write-Warning "[1/4] backend/.env.example not found!"
    }
} else {
    Write-Host "[1/4] backend/.env already exists." -ForegroundColor Green
}

# 2. Check and copy frontend .env if missing
if (-not (Test-Path "frontend\.env")) {
    if (Test-Path "frontend\.env.example") {
        Write-Host "[2/4] Creating frontend/.env from frontend/.env.example..." -ForegroundColor Yellow
        Copy-Item "frontend\.env.example" "frontend\.env"
        Write-Host "       frontend/.env created successfully." -ForegroundColor Green
    } else {
        Write-Warning "[2/4] frontend/.env.example not found!"
    }
} else {
    Write-Host "[2/4] frontend/.env already exists." -ForegroundColor Green
}

# 3. Check Python & backend dependencies
Write-Host "[3/4] Checking Python backend dependencies..." -ForegroundColor Cyan
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Error "Python is not installed or not in PATH! Please install Python 3.10+ from https://www.python.org/"
    exit 1
}

$depsInstalled = $true
try {
    python -c "import fastapi, uvicorn, groq, supabase" 2>$null
    if ($LASTEXITCODE -ne 0) { $depsInstalled = $false }
} catch {
    $depsInstalled = $false
}

if (-not $depsInstalled) {
    Write-Host "       Installing backend dependencies from backend/requirements.txt..." -ForegroundColor Yellow
    python -m pip install -r backend/requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install backend dependencies!"
        exit 1
    }
} else {
    Write-Host "       Backend dependencies verified." -ForegroundColor Green
}

# 4. Check Node.js and frontend dependencies
Write-Host "[4/4] Checking Node.js dependencies..." -ForegroundColor Cyan
$npmCmd = Get-Command npm -ErrorAction SilentlyContinue
if (-not $npmCmd) {
    Write-Error "Node.js / npm is not installed or not in PATH! Please install Node.js LTS from https://nodejs.org/"
    exit 1
}

if (-not (Test-Path "frontend\node_modules")) {
    Write-Host "       Installing frontend dependencies in frontend/..." -ForegroundColor Yellow
    Push-Location frontend
    npm install
    Pop-Location
} else {
    Write-Host "       Frontend dependencies verified." -ForegroundColor Green
}

if (-not (Test-Path "node_modules\concurrently")) {
    Write-Host "       Installing concurrently in project root..." -ForegroundColor Yellow
    npm install
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "Starting servers:" -ForegroundColor Cyan
Write-Host "  - Backend:  http://0.0.0.0:8000 (API & Swagger at /docs)" -ForegroundColor Green
Write-Host "  - Frontend: http://0.0.0.0:5173" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

try {
    npm run dev:all
} catch {
    Write-Warning "npm run dev:all stopped or encountered an error. Launching fallback processes..."
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$ScriptDir\backend'; python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$ScriptDir\frontend'; npm run dev -- --host 0.0.0.0 --port 5173"
}
