@echo off
setlocal enabledelayedexpansion

title BRD Agent - Development Setup
cd /d "%~dp0"

echo ================================================================
echo               BRD Agent - One-Click Dev Setup
echo ================================================================
echo.

:: 1. Check & copy backend .env if missing
if not exist "backend\.env" (
    if exist "backend\.env.example" (
        echo [1/4] Creating backend\.env from backend\.env.example...
        copy "backend\.env.example" "backend\.env" >nul
        echo        backend\.env created successfully.
    ) else (
        echo [1/4] WARNING: backend\.env.example not found!
    )
) else (
    echo [1/4] backend\.env already exists.
)

:: 2. Check & copy frontend .env if missing
if not exist "frontend\.env" (
    if exist "frontend\.env.example" (
        echo [2/4] Creating frontend\.env from frontend\.env.example...
        copy "frontend\.env.example" "frontend\.env" >nul
        echo        frontend\.env created successfully.
    ) else (
        echo [2/4] WARNING: frontend\.env.example not found!
    )
) else (
    echo [2/4] frontend\.env already exists.
)

:: 3. Check Python and backend dependencies
echo [3/4] Checking Python backend dependencies...
python --version >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)

python -c "import fastapi, uvicorn, groq, supabase" >nul 2>nul
if %errorlevel% neq 0 (
    echo        Missing backend dependencies. Installing from backend\requirements.txt...
    python -m pip install -r backend\requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install backend dependencies!
        pause
        exit /b 1
    )
) else (
    echo        Backend dependencies verified.
)

:: 4. Check Node.js and frontend dependencies
echo [4/4] Checking Node.js dependencies...
call npm --version >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js / npm is not installed or not in PATH!
    echo Please install Node.js LTS from https://nodejs.org/
    pause
    exit /b 1
)

if not exist "frontend\node_modules" (
    echo        Installing frontend dependencies in frontend\...
    pushd frontend
    call npm install
    popd
) else (
    echo        Frontend dependencies verified.
)

if not exist "node_modules\concurrently" (
    echo        Installing concurrently in project root...
    call npm install
)

echo.
echo ================================================================
echo Starting servers:
echo   - Backend:  http://0.0.0.0:8000 (API and Swagger at /docs)
echo   - Frontend: http://0.0.0.0:5173
echo ================================================================
echo.

:: Launch servers using concurrently
call npm run dev:all
if %errorlevel% neq 0 (
    echo.
    echo npm run dev:all stopped or encountered an error.
    echo Attempting fallback: Launching backend and frontend in separate windows...
    start "BRD Agent Backend (Port 8000)" cmd /k "cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
    start "BRD Agent Frontend (Port 5173)" cmd /k "cd frontend && npm run dev -- --host 0.0.0.0 --port 5173"
)
