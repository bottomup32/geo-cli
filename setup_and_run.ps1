param(
    [switch]$SkipInstall = $false,
    [string]$QueriesFile = "",
    [switch]$Worker = $false,
    [string]$Server = "https://geo-cli.onrender.com",
    [string]$ApiKey = ""
)

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " GEO CLI 로컬 실행 환경 준비 및 실행 스크립트" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

if (-not $SkipInstall) {
    Write-Host "`n[1/3] 패키지 의존성 설치 중 (pip install -e .)..." -ForegroundColor Yellow
    pip install -e .
    
    Write-Host "`n[2/3] Playwright Chromium 브라우저 설치 중..." -ForegroundColor Yellow
    playwright install chromium
} else {
    Write-Host "`n[INFO] 설치 단계를 건너뜁니다." -ForegroundColor DarkGray
}

Write-Host "`n[3/3] GEO CLI 실행을 시작합니다..." -ForegroundColor Green
Write-Host "---------------------------------------------" -ForegroundColor DarkGray

# 실행 모드 분기
if ($Worker) {
    Write-Host "[Worker 모드 — 클라우드 자동 연동]" -ForegroundColor Magenta
    $workerArgs = @("--server", $Server)
    if ($ApiKey -ne "") {
        $workerArgs += @("--api-key", $ApiKey)
    }
    python -m geo_cli.local_worker @workerArgs
} elseif ($QueriesFile -ne "") {
    Write-Host "[웹에서 다운로드한 부분 평가 모드]" -ForegroundColor Magenta
    python -m geo_cli.run_local_test "$QueriesFile"
} else {
    Write-Host "[로컬 전체 파이프라인 모드]" -ForegroundColor Magenta
    python -m geo_cli
}

Write-Host "`n=============================================" -ForegroundColor Cyan
Write-Host " 실행이 완료되거나 중단되었습니다." -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
