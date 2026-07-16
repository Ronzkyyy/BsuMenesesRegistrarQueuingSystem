# Starts the BSU Registrar Queue System for local development:
# backend (FastAPI + PostgreSQL) and frontend (Vite) each in their own window.
# Safe to re-run - it only installs/seeds what's missing.

$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$venvPython = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating backend virtual environment..." -ForegroundColor Yellow
    python -m venv (Join-Path $backend ".venv")
    & $venvPython -m pip install --upgrade pip -q
    & $venvPython -m pip install -r (Join-Path $backend "requirements.txt")
}

$envFile = Join-Path $backend ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "Creating backend/.env (local SQLite config)..." -ForegroundColor Yellow
    @"
DATABASE_URL=sqlite:///./bsu_queue.db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=dev-only-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
DEBUG=True
LOG_LEVEL=info
"@ | Set-Content $envFile
}

$dbFile = Join-Path $backend "bsu_queue.db"
if (-not (Test-Path $dbFile)) {
    Write-Host "Seeding database with dummy accounts and sample data..." -ForegroundColor Yellow
    Push-Location $backend
    & $venvPython seed.py
    Pop-Location
}

$nodeModules = Join-Path $frontend "node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    Push-Location $frontend
    npm install
    Pop-Location
}

Write-Host "Starting backend on http://localhost:8000 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backend'; & '$venvPython' -m uvicorn app.main:app --port 8000"

Write-Host "Starting frontend on http://localhost:5173 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$frontend'; npm run dev"

Write-Host ""
Write-Host "Backend:      http://localhost:8000" -ForegroundColor Green
Write-Host "Frontend:     http://localhost:5173" -ForegroundColor Green
Write-Host "Admin login:  admin / admin123  (or registrar/registrar123, staff/staff123)" -ForegroundColor Green
Write-Host ""
Write-Host "Each server runs in its own window - close the window or Ctrl+C inside it to stop." -ForegroundColor DarkGray
