#Requires -Version 5.1
<#
.SYNOPSIS
  일햇음청년 제조기 — Windows 초기 환경 자동 구성 (Python 백엔드, OCR, 프론트, Ollama 선택).

.PARAMETER SkipOllama
  Ollama 설치/모델 pull 생략

.PARAMETER SkipOcr
  EasyOCR 등 requirements-ocr.txt 설치 생략 (용량·시간 절약)

.PARAMETER SkipFrontend
  npm install 생략

.PARAMETER SkipPrereqInstall
  winget 으로 Python·Node 자동 설치 시도 생략(수동 설치만 안내)
#>
param(
    [switch]$SkipOllama,
    [switch]$SkipOcr,
    [switch]$SkipFrontend,
    [switch]$SkipPrereqInstall
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Refresh-SessionPath {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Resolve-PythonExe {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $out = & py -3 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) { return $out.Trim() }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $out = & python -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) { return $out.Trim() }
    }
    return $null
}

function Test-WingetAvailable {
    return [bool](Get-Command winget -ErrorAction SilentlyContinue)
}

function Invoke-WingetPackageInstall([string]$PackageId) {
    if (-not (Test-WingetAvailable)) {
        Write-Warning "winget 이 없습니다. Store 정책·회사 PC 제한일 수 있습니다."
        return $false
    }
    Write-Host "winget install: $PackageId" -ForegroundColor Yellow
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        & winget install -e --id $PackageId --accept-package-agreements --accept-source-agreements 2>&1 | Out-Host
    } finally {
        $ErrorActionPreference = $prev
    }
    return $true
}

Write-Host "=== 일햇음청년 제조기 — 로컬 설치 ===" -ForegroundColor Cyan
Write-Host "저장소: $RepoRoot"

$pythonExe = Resolve-PythonExe
if (-not $pythonExe -and -not $SkipPrereqInstall) {
    Write-Host "Python 3 가 PATH 에 없습니다. winget 으로 설치를 시도합니다..." -ForegroundColor Yellow
    foreach ($pkg in @("Python.Python.3.12", "Python.Python.3.11")) {
        if (-not (Test-WingetAvailable)) { break }
        Invoke-WingetPackageInstall $pkg | Out-Null
        Refresh-SessionPath
        Start-Sleep -Seconds 5
        $pythonExe = Resolve-PythonExe
        if ($pythonExe) { break }
    }
}
if (-not $pythonExe) {
    Write-Host ""
    Write-Host "Python 3 를 찾을 수 없습니다. 아래 중 하나를 진행한 뒤, 새 PowerShell 을 연 다음 다시 setup.ps1 을 실행하세요." -ForegroundColor Red
    Write-Host "  - https://www.python.org/downloads/  설치 시 'Add python.exe to PATH' 체크" -ForegroundColor Gray
    Write-Host "  - 또는 관리자 PowerShell: winget install -e --id Python.Python.3.12" -ForegroundColor Gray
    Write-Host "  - 자동 설치 시도를 끄려면: -SkipPrereqInstall" -ForegroundColor Gray
    throw "Python 3 가 필요합니다."
}
Write-Host "Python: $pythonExe"

$backend = Join-Path $RepoRoot "backend"
$venvPy = Join-Path $backend ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "가상환경 생성: backend\.venv" -ForegroundColor Yellow
    & $pythonExe -m venv (Join-Path $backend ".venv")
}
if (-not (Test-Path $venvPy)) {
    throw "가상환경 생성에 실패했습니다."
}

Write-Host "pip 업그레이드 및 requirements 설치..." -ForegroundColor Yellow
& $venvPy -m pip install --upgrade pip wheel
& $venvPy -m pip install -r (Join-Path $backend "requirements.txt")
if (-not $SkipOcr) {
    Write-Host "OCR 의존성 설치 (시간이 걸릴 수 있음)..." -ForegroundColor Yellow
    & $venvPy -m pip install -r (Join-Path $backend "requirements-ocr.txt")
} else {
    Write-Host "OCR 건너뜀 (-SkipOcr). 필요 시: pip install -r backend\requirements-ocr.txt" -ForegroundColor DarkYellow
}

Write-Host "NLTK 데이터 사전 내려받기 (RAKE 등)..." -ForegroundColor Yellow
# PS 5.1 + UTF-8 무BOM 저장소에서 python -c @" ... "@ 는 파서가 깨질 수 있어 임시 .py 로 실행
$nltkPy = Join-Path $env:TEMP ("job-assistant-nltk-{0}.py" -f [guid]::NewGuid().ToString("N"))
@(
    'import nltk',
    'for pkg in ("punkt", "punkt_tab", "stopwords"):',
    '    try:',
    '        nltk.download(pkg, quiet=True)',
    '    except Exception as e:',
    '        print("nltk", pkg, e)'
) | Set-Content -LiteralPath $nltkPy -Encoding ASCII
try {
    & $venvPy $nltkPy
} finally {
    Remove-Item -LiteralPath $nltkPy -Force -ErrorAction SilentlyContinue
}

$envExample = Join-Path $backend ".env.example"
$envFile = Join-Path $backend ".env"
if (-not (Test-Path $envFile) -and (Test-Path $envExample)) {
    Copy-Item $envExample $envFile
    Write-Host "backend\.env 생성 (.env.example 복사)" -ForegroundColor Green
} elseif (Test-Path $envFile) {
    Write-Host "backend\.env 이미 있음 — 덮어쓰지 않음" -ForegroundColor DarkGray
}

if (-not $SkipOllama) {
    Refresh-SessionPath
    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $ollama) {
        $winget = Get-Command winget -ErrorAction SilentlyContinue
        if ($winget) {
            Write-Host "Ollama winget 설치 시도..." -ForegroundColor Yellow
            try {
                & winget install -e --id Ollama.Ollama --accept-package-agreements --accept-source-agreements
            } catch {
                Write-Warning "winget으로 Ollama 설치 실패: $_ 수동 설치: https://ollama.com/download"
            }
            Refresh-SessionPath
            Start-Sleep -Seconds 2
        } else {
            Write-Warning "winget 없음. Ollama 수동 설치: https://ollama.com/download"
        }
    }
    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    if ($ollama) {
        $model = "llama3:latest"
        Write-Host "Ollama 모델 pull: $model (backend 기본값과 맞춤)" -ForegroundColor Yellow
        try {
            & ollama pull $model
        } catch {
            Write-Warning "ollama pull 실패. Ollama 앱을 실행한 뒤 터미널에서: ollama pull $model"
        }
    } else {
        Write-Warning "ollama 명령을 찾을 수 없습니다. 설치 후 새 터미널에서 ollama serve / pull 을 실행하세요."
    }
} else {
    Write-Host "Ollama 건너뜀 (-SkipOllama)" -ForegroundColor DarkYellow
}

if (-not $SkipFrontend) {
    $node = Get-Command node -ErrorAction SilentlyContinue
    if (-not $node -and -not $SkipPrereqInstall) {
        Write-Host "Node.js 가 PATH 에 없습니다. winget 으로 LTS 설치를 시도합니다..." -ForegroundColor Yellow
        Invoke-WingetPackageInstall "OpenJS.NodeJS.LTS" | Out-Null
        Refresh-SessionPath
        Start-Sleep -Seconds 5
        $node = Get-Command node -ErrorAction SilentlyContinue
    }
    if (-not $node) {
        Write-Warning "Node.js 없음 — https://nodejs.org/ LTS 설치 후 다시 실행하거나 -SkipFrontend 로 백엔드만 구성하세요."
    } else {
        $fe = Join-Path $RepoRoot "frontend"
        Push-Location $fe
        try {
            if (-not (Test-Path (Join-Path $fe "node_modules"))) {
                Write-Host "npm install (frontend)..." -ForegroundColor Yellow
                npm install
            } else {
                Write-Host "frontend\node_modules 존재 — npm install 생략" -ForegroundColor DarkGray
            }
            $feEnvEx = Join-Path $fe ".env.local.example"
            $feEnv = Join-Path $fe ".env.local"
            if (-not (Test-Path $feEnv) -and (Test-Path $feEnvEx)) {
                Copy-Item $feEnvEx $feEnv
                Write-Host "frontend\.env.local 생성" -ForegroundColor Green
            }
        } finally {
            Pop-Location
        }
    }
}

Write-Host ""
Write-Host "설치 완료." -ForegroundColor Green
Write-Host "  백엔드: cd backend; .\.venv\Scripts\activate; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
Write-Host "  프론트: cd frontend; npm run dev"
Write-Host "  API 문서: http://127.0.0.1:8000/docs"
Write-Host "자세한 사용법은 README.md 를 참고하세요."
