#Requires -Version 5.1
<#
.SYNOPSIS
  Job assistant: run setup.ps1 then start backend (uvicorn) and frontend (npm run dev).

.DESCRIPTION
  Default: setup.ps1, free ports 8000/3000, open two new PowerShell windows.
  -SameWindow: hidden cmd batch, health-check localhost, then kill process trees (smoke test).

.PARAMETER SkipSetup
  Skip scripts\setup.ps1 (use when already installed).

.PARAMETER SameWindow
  Smoke test in this session (no new windows).
#>
param(
    [switch]$SkipSetup,
    [switch]$SkipOllama,
    [switch]$SkipOcr,
    [switch]$SkipFrontend,
    [switch]$SameWindow,
    [switch]$NoKillPorts
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Stop-PortListeners([int]$Port, [int]$Rounds = 6) {
    for ($r = 1; $r -le $Rounds; $r++) {
        $pids = @(
            Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique |
            Where-Object { $_ -gt 0 }
        )
        if (-not $pids -or $pids.Count -eq 0) { return }
        foreach ($listenerPid in $pids) {
            Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 1
    }
}

Write-Host "=== install and run (local) ===" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"

if (-not $SkipSetup) {
    $setupPath = Join-Path $RepoRoot "scripts\setup.ps1"
    $setupArgs = @()
    if ($SkipOllama) { $setupArgs += "-SkipOllama" }
    if ($SkipOcr) { $setupArgs += "-SkipOcr" }
    if ($SkipFrontend) { $setupArgs += "-SkipFrontend" }
    Write-Host "Running: setup.ps1 $($setupArgs -join ' ')" -ForegroundColor Yellow
    & $setupPath @setupArgs
} else {
    Write-Host "SkipSetup: not running setup.ps1" -ForegroundColor DarkYellow
}

$venvPy = Join-Path $RepoRoot "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    throw "Missing backend\.venv\Scripts\python.exe. Run without -SkipSetup."
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw "Node.js not on PATH. Install LTS from https://nodejs.org/"
}

$backend = Join-Path $RepoRoot "backend"
$frontend = Join-Path $RepoRoot "frontend"

if (-not $NoKillPorts) {
    Write-Host "Stopping listeners on ports 8000 and 3000..." -ForegroundColor Yellow
    Stop-PortListeners 8000
    Stop-PortListeners 3000
    Start-Sleep -Seconds 1
}

if ($SameWindow) {
    Write-Host "SameWindow: start backend and frontend, then health check." -ForegroundColor Yellow
    $beBat = Join-Path $env:TEMP "job-assistant-run-be-$(Get-Random).bat"
    $feBat = Join-Path $env:TEMP "job-assistant-run-fe-$(Get-Random).bat"
    @(
        '@echo off',
        "set PYTHONPATH=$backend",
        "cd /d `"$backend`"",
        "`"$venvPy`" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
    ) | Set-Content -LiteralPath $beBat -Encoding ASCII
    @(
        '@echo off',
        "cd /d `"$frontend`"",
        'call npm run dev'
    ) | Set-Content -LiteralPath $feBat -Encoding ASCII

    $procBe = Start-Process -FilePath $beBat -PassThru -WindowStyle Hidden
    if (-not $procBe) { throw "Failed to start backend process" }

    $okBe = $false
    $deadline = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $deadline) {
        try {
            $h = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 3 -ErrorAction Stop
            if ($h.status -eq "ok") {
                $okBe = $true
                break
            }
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    if (-not $okBe) {
        taskkill /PID $procBe.Id /T /F 2>$null | Out-Null
        throw "GET http://127.0.0.1:8000/api/health did not succeed within 120s"
    }
    Write-Host "Backend OK: /api/health" -ForegroundColor Green

    $procFe = Start-Process -FilePath $feBat -PassThru -WindowStyle Hidden
    if (-not $procFe) {
        taskkill /PID $procBe.Id /T /F 2>$null | Out-Null
        throw "Failed to start frontend process"
    }

    $okFe = $false
    $deadline2 = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $deadline2) {
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:3000" -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
            if ($r.StatusCode -eq 200) {
                $okFe = $true
                break
            }
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    if (-not $okFe) {
        taskkill /PID $procFe.Id /T /F 2>$null | Out-Null
        taskkill /PID $procBe.Id /T /F 2>$null | Out-Null
        throw "GET http://localhost:3000 did not return 200 within 120s"
    }
    Write-Host "Frontend OK: http://localhost:3000" -ForegroundColor Green

    Write-Host "SameWindow: stopping process trees." -ForegroundColor Yellow
    taskkill /PID $procFe.Id /T /F 2>$null | Out-Null
    taskkill /PID $procBe.Id /T /F 2>$null | Out-Null
    Start-Sleep -Seconds 2
    Write-Host "Smoke test done." -ForegroundColor Green
    return
}

$cfgPath = Join-Path $env:TEMP ("job-assistant-run-{0}.json" -f [guid]::NewGuid().ToString("N"))
(@{ backend = $backend; venvPy = $venvPy; frontend = $frontend } | ConvertTo-Json -Compress) |
    Set-Content -LiteralPath $cfgPath -Encoding UTF8

$beScript = Join-Path $env:TEMP "job-assistant-backend-$(Get-Random).ps1"
$feScript = Join-Path $env:TEMP "job-assistant-frontend-$(Get-Random).ps1"

$cfgPathB64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($cfgPath))
$nl = [Environment]::NewLine
$beScriptBody =
    ('$cfgPath = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String(''' + $cfgPathB64 + '''))' + $nl) +
    ('$cfg = Get-Content -Raw -LiteralPath $cfgPath | ConvertFrom-Json' + $nl) +
    ('Set-Location -LiteralPath $cfg.backend' + $nl) +
    ('$env:PYTHONPATH = $cfg.backend' + $nl) +
    ('Write-Host ''API http://127.0.0.1:8000/docs'' -ForegroundColor Cyan' + $nl) +
    ('& $cfg.venvPy -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload' + $nl)
$beScriptBody | Set-Content -LiteralPath $beScript -Encoding UTF8

$feScriptBody =
    ('$cfgPath = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String(''' + $cfgPathB64 + '''))' + $nl) +
    ('$cfg = Get-Content -Raw -LiteralPath $cfgPath | ConvertFrom-Json' + $nl) +
    ('Set-Location -LiteralPath $cfg.frontend' + $nl) +
    ('Write-Host ''Web http://localhost:3000'' -ForegroundColor Cyan' + $nl) +
    ('npm run dev' + $nl)
$feScriptBody | Set-Content -LiteralPath $feScript -Encoding UTF8

$beArgs = @('-NoExit', '-NoProfile', '-File', $beScript)
Start-Process -FilePath 'powershell.exe' -ArgumentList $beArgs
Start-Sleep -Milliseconds 500
$feArgs = @('-NoExit', '-NoProfile', '-File', $feScript)
Start-Process -FilePath 'powershell.exe' -ArgumentList $feArgs

Write-Host ''
Write-Host 'Started backend and frontend in new windows.' -ForegroundColor Green
Write-Host '  API:  http://127.0.0.1:8000/docs'
Write-Host '  Web:  http://localhost:3000'
Write-Host 'Close each window with Ctrl+C when done.'
Write-Host ('Temp files: ' + $beScript + ' | ' + $feScript + ' | ' + $cfgPath)
