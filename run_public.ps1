# run_public.ps1
# Starts GEO CLI and exposes it to the internet via ngrok or localtunnel.

param(
    [switch]$SkipBuild = $false,
    [ValidateSet("ngrok","localtunnel")]
    [string]$Tunnel = "ngrok"
)

$PORT = 8000

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " GEO CLI v2.0 - Public Access Script" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# -- Detect local and public IP --
$localIp = "localhost"
try {
    $ipInfo = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
              Where-Object { $_.IPAddress -match "^192\.168\.|^10\.|^172\.1[6-9]\.|^172\.2[0-9]\.|^172\.3[0-1]\." }
    if ($ipInfo) { $localIp = ($ipInfo | Select-Object -First 1).IPAddress }
} catch {}

$publicIp = "(unknown)"
try {
    $publicIp = (curl.exe -s --max-time 4 ifconfig.me).Trim()
} catch {}

# -- Step 1: Show access info --
Write-Host "[Step 1] Access addresses" -ForegroundColor Yellow
Write-Host "  Same WiFi  :  http://$localIp`:$PORT" -ForegroundColor Green
Write-Host "  Public IP  :  http://$publicIp`:$PORT  (requires port forwarding)" -ForegroundColor Green
Write-Host "  Tunnel URL :  see Step 3 below" -ForegroundColor Green
Write-Host ""

# -- Step 2: Start server if not running --
Write-Host "[Step 2] Checking server status..." -ForegroundColor Yellow

$running = $false
try {
    if (netstat -ano | Select-String ":$PORT .*LISTENING") { $running = $true }
} catch {}

if ($running) {
    Write-Host "  Server already running on port $PORT." -ForegroundColor Gray
} else {
    Write-Host "  Starting server..." -ForegroundColor Yellow

    if ($SkipBuild) {
        Start-Process powershell -ArgumentList @(
            "-ExecutionPolicy", "Bypass",
            "-Command",
            "cd '$PWD'; uvicorn backend.main:app --host 0.0.0.0 --port $PORT"
        ) -WindowStyle Normal
    } else {
        Start-Process powershell -ArgumentList @(
            "-ExecutionPolicy", "Bypass",
            "-File", ".\setup_and_run.ps1",
            "-SkipInstall"
        ) -WindowStyle Normal
    }

    Write-Host "  Waiting for server to start (10s)..." -ForegroundColor DarkGray
    Start-Sleep -Seconds 10

    $ready = $false
    for ($i = 0; $i -lt 6; $i++) {
        try {
            Invoke-WebRequest -Uri "http://localhost:$PORT" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop | Out-Null
            $ready = $true
            break
        } catch {
            Write-Host "  Waiting... ($($i+1)/6)" -ForegroundColor DarkGray
            Start-Sleep -Seconds 3
        }
    }

    if ($ready) {
        Write-Host "  Server is ready!" -ForegroundColor Green
    } else {
        Write-Host "  Server not responding. Check manually: http://localhost:$PORT" -ForegroundColor Red
    }
}

Write-Host ""

# -- Step 3: Create tunnel --
Write-Host "[Step 3] Creating public tunnel ($Tunnel)..." -ForegroundColor Yellow
Write-Host ""

if ($Tunnel -eq "ngrok") {
    $ngrokPath = Get-Command ngrok -ErrorAction SilentlyContinue
    if (-not $ngrokPath) {
        Write-Host "  ngrok not found. Install: winget install ngrok.ngrok" -ForegroundColor Red
        Write-Host "  Falling back to localtunnel..." -ForegroundColor DarkGray
        npx --yes localtunnel --port $PORT
    } else {
        Write-Host "  Starting ngrok..." -ForegroundColor DarkGray

        # Stop any existing ngrok process
        Get-Process -Name "ngrok" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1

        # Start ngrok in background
        Start-Process ngrok -ArgumentList "http $PORT" -WindowStyle Hidden

        # Read URL from ngrok local API (wait up to 15s)
        $tunnelUrl = $null
        for ($i = 0; $i -lt 15; $i++) {
            Start-Sleep -Seconds 1
            try {
                $info = Invoke-RestMethod -Uri "http://localhost:4040/api/tunnels" -ErrorAction Stop
                $tunnelUrl = ($info.tunnels | Where-Object { $_.proto -eq "https" } | Select-Object -First 1).public_url
                if ($tunnelUrl) { break }
            } catch {}
        }

        if ($tunnelUrl) {
            Write-Host ""
            Write-Host "==========================================================" -ForegroundColor Green
            Write-Host "  PUBLIC URL (accessible from anywhere)" -ForegroundColor Green
            Write-Host ""
            Write-Host "  $tunnelUrl" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "  Share this URL with your clients." -ForegroundColor Gray
            Write-Host "  Closing this window will stop the tunnel." -ForegroundColor DarkGray
            Write-Host "  ngrok dashboard: http://localhost:4040" -ForegroundColor DarkGray
            Write-Host "==========================================================" -ForegroundColor Green
            Write-Host ""
            Write-Host "  Press any key to stop the tunnel..." -ForegroundColor DarkGray
            $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
            Get-Process -Name "ngrok" -ErrorAction SilentlyContinue | Stop-Process -Force
        } else {
            Write-Host "  Could not get tunnel URL." -ForegroundColor Red
            Write-Host "  Check ngrok dashboard: http://localhost:4040" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "  NOTE: localtunnel will ask for a password in the browser." -ForegroundColor DarkYellow
    Write-Host "  Password: $publicIp" -ForegroundColor Cyan
    Write-Host ""
    npx --yes localtunnel --port $PORT
}
