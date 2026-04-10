# 백엔드 단일 인스턴스 기동 (포트 8000 에 uvicorn 이 여러 개 떠 있으면 요청이 구버전으로 갈 수 있음)
param(
    [int]$Port = 8000
)
$ErrorActionPreference = "SilentlyContinue"
$backendRoot = $PSScriptRoot
Set-Location $backendRoot
$env:PYTHONPATH = $backendRoot

# $pid 는 PowerShell 자동 변수 $PID 와 동일해 루프 변수로 쓰면 안 됨
Write-Host "Port $Port 리스너 전부 종료 시도 (최대 5회)..."
for ($round = 1; $round -le 5; $round++) {
    $pids = @(
        Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique |
        Where-Object { $_ -gt 0 }
    )
    if (-not $pids -or $pids.Count -eq 0) { break }
    foreach ($listenerPid in $pids) {
        Write-Host "  Stop-Process -Id $listenerPid"
        Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 1
}

$still = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
if ($still) {
    Write-Host "경고: 포트 $Port 에 아직 LISTEN 프로세스가 있습니다: $($still -join ', '). 작업 관리자에서 python 종료 후 다시 실행하세요."
}

Start-Sleep -Seconds 1

Write-Host "Uvicorn 시작: http://127.0.0.1:$Port (API: /api/health)"
Write-Host "확인: 브라우저에서 http://127.0.0.1:$Port/ 열 때 diagnostics.post_collect_suggestions_registered 가 true 여야 최신 코드입니다."
python -m uvicorn app.main:app --host 127.0.0.1 --port $Port --reload
