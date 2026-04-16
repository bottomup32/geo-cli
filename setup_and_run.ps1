param(
    [switch]$SkipInstall = $false,
    [switch]$DevMode = $false,
    [switch]$Legacy = $false
)

$ErrorActionPreference = "Stop"

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " GEO CLI v2.0" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# ── Legacy mode ──────────────────────────────────────────
if ($Legacy) {
    if (-not $SkipInstall) {
        Write-Host "`n[1/3] Installing packages..." -ForegroundColor Yellow
        pip install -e .
        Write-Host "`n[2/3] Installing Playwright..." -ForegroundColor Yellow
        python -m playwright install chromium
    }
    Write-Host "`n[3/3] Starting Streamlit UI (legacy)..." -ForegroundColor Green
    Write-Host "URL: http://localhost:8501" -ForegroundColor Green
    streamlit run app.py
    exit 0
}

# ── Prerequisites ────────────────────────────────────────
Write-Host "`n[0/5] Checking prerequisites..." -ForegroundColor Yellow

try {
    $pythonVer = python --version 2>&1
    Write-Host "  Python: $pythonVer" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Python not found. Install 3.11+ from python.org" -ForegroundColor Red
    exit 1
}

try {
    $nodeVer = node --version 2>&1
    Write-Host "  Node.js: $nodeVer" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Node.js not found. Install 18+ from nodejs.org" -ForegroundColor Red
    exit 1
}

# ── Install ──────────────────────────────────────────────
if (-not $SkipInstall) {
    Write-Host "`n[1/5] Installing Python packages..." -ForegroundColor Yellow
    pip install -e '.[web]'

    Write-Host "`n[2/5] Installing Playwright Chromium..." -ForegroundColor Yellow
    python -m playwright install chromium

    Write-Host "`n[3/5] Installing React frontend packages..." -ForegroundColor Yellow
    Push-Location frontend
    npm install
    Pop-Location
} else {
    Write-Host "`n[INFO] Skipping install steps." -ForegroundColor DarkGray
}

# ── DB init ──────────────────────────────────────────────
Write-Host "`n[4/5] Initializing database..." -ForegroundColor Yellow
python -c 'from backend.database.engine import init_db; init_db()'

$dataFiles = Get-ChildItem -Path "data" -Filter "brief_*.json" -ErrorAction SilentlyContinue
if ($dataFiles.Count -gt 0) {
    Write-Host "  Found $($dataFiles.Count) existing briefs - migrating to DB..." -ForegroundColor Yellow
    python -c 'from backend.database.migrate_files import migrate_existing_data; migrate_existing_data()'
}

# ── .env file ────────────────────────────────────────────
if (-not (Test-Path ".env")) {
    Write-Host "`n  Creating .env file..." -ForegroundColor Yellow
    $envContent = @'
ANTHROPIC_API_KEY=
GEO_MODEL=claude-sonnet-4-6
GEO_DATA_DIR=./data
'@
    $envContent | Out-File -FilePath ".env" -Encoding utf8
    Write-Host "  .env created. Please enter your API key." -ForegroundColor Yellow
}

# ── Run ──────────────────────────────────────────────────
Write-Host "`n[5/5] Starting server..." -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Cyan

if ($DevMode) {
    Write-Host " Dev Mode (Hot Reload)" -ForegroundColor Yellow
    Write-Host " Backend:  http://localhost:8000" -ForegroundColor Green
    Write-Host " Frontend: http://localhost:5173" -ForegroundColor Green
    Write-Host " API Docs: http://localhost:8000/docs" -ForegroundColor Green
    Write-Host "=============================================" -ForegroundColor Cyan

    # Backend in separate terminal (GEO_DEV_MODE disables static SPA mount)
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; `$env:GEO_DEV_MODE='1'; uvicorn backend.main:app --reload --port 8000"
    # Frontend in current terminal
    Push-Location frontend
    npm run dev
    Pop-Location
} else {
    Write-Host " Production Mode (single server)" -ForegroundColor Green
    Write-Host " URL: http://localhost:8000" -ForegroundColor Green
    Write-Host " API Docs: http://localhost:8000/docs" -ForegroundColor Green
    Write-Host "=============================================" -ForegroundColor Cyan

    # Build frontend
    Write-Host "`nBuilding frontend..." -ForegroundColor Yellow
    Push-Location frontend
    npm run build
    Pop-Location

    # Run FastAPI (serves built SPA)
    uvicorn backend.main:app --host 0.0.0.0 --port 8000
}

Write-Host "`n=============================================" -ForegroundColor Cyan
Write-Host " Done." -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
