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

function Write-SetupPhase {
    param(
        [Parameter(Mandatory = $true)][string]$Title,
        [string]$Hint = ""
    )
    Write-Host ""
    Write-Host "------------------------------------------------------------" -ForegroundColor DarkCyan
    Write-Host ("[{0}]  {1}" -f (Get-Date -Format "HH:mm:ss"), $Title) -ForegroundColor Cyan
    if ($Hint) { Write-Host ("       {0}" -f $Hint) -ForegroundColor DarkGray }
    Write-Host "------------------------------------------------------------" -ForegroundColor DarkCyan
}

function Write-SetupPhaseDone([string]$Title) {
    Write-Host ("[{0}]  완료: {1}" -f (Get-Date -Format "HH:mm:ss"), $Title) -ForegroundColor Green
}

function Refresh-SessionPath {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Test-IsWindowsStorePythonAlias([string]$path) {
    if (-not $path) { return $false }
    # 설정 > 앱 > 앱 실행 별칭 의 Store용 python.exe (실제 인터프리터 아님)
    if ($path -match '\\Microsoft\\WindowsApps\\') { return $true }
    if ($path -match '\\WindowsApps\\python(3)?\.exe$') { return $true }
    return $false
}

function Add-RealPythonDirsToSessionPath {
    $dirs = @(
        (Join-Path $env:LocalAppData "Programs\Python\Python312"),
        (Join-Path $env:LocalAppData "Programs\Python\Python311"),
        (Join-Path $env:LocalAppData "Programs\Python\Python310"),
        "C:\Python312",
        "C:\Python311"
    )
    foreach ($d in $dirs) {
        $py = Join-Path $d "python.exe"
        if (-not (Test-Path -LiteralPath $py)) { continue }
        $parts = @($env:Path -split ';' | Where-Object { $_ })
        if ($parts -notcontains $d) { $env:Path = "$d;$env:Path" }
        $scripts = Join-Path $d "Scripts"
        if (Test-Path -LiteralPath $scripts) {
            $parts2 = @($env:Path -split ';' | Where-Object { $_ })
            if ($parts2 -notcontains $scripts) { $env:Path = "$scripts;$env:Path" }
        }
    }
}

function Resolve-PythonExe {
    Add-RealPythonDirsToSessionPath
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $out = & py -3 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) { return $out.Trim() }
    }
    $pyCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pyCmd) {
        $src = $pyCmd.Source
        if (Test-IsWindowsStorePythonAlias $src) {
            return $null
        }
        $out = & $src -c "import sys; print(sys.executable)" 2>$null
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

Write-SetupPhase "Python 확인" "PATH 새로고침, Store python 별칭 제외, winget 설치 시도(옵션)"
Refresh-SessionPath
Add-RealPythonDirsToSessionPath
$pythonExe = Resolve-PythonExe
if (-not $pythonExe -and -not $SkipPrereqInstall) {
    Write-Host "Python 3 가 PATH 에 없습니다. winget 으로 설치를 시도합니다..." -ForegroundColor Yellow
    foreach ($pkg in @("Python.Python.3.12", "Python.Python.3.11")) {
        if (-not (Test-WingetAvailable)) { break }
        Write-Host "  -> winget 패키지: $pkg" -ForegroundColor DarkYellow
        Invoke-WingetPackageInstall $pkg | Out-Null
        Refresh-SessionPath
        Add-RealPythonDirsToSessionPath
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
    Write-Host "  - Windows 설정 > 앱 > 고급 앱 설정 > 앱 실행 별칭 에서 python.exe 별칭 끄기 (Store 허위 python 방지)" -ForegroundColor Gray
    Write-Host "  - 자동 설치 시도를 끄려면: -SkipPrereqInstall" -ForegroundColor Gray
    throw "Python 3 가 필요합니다."
}
Write-SetupPhaseDone "Python 확인"
Write-Host "Python: $pythonExe"

$backend = Join-Path $RepoRoot "backend"
$venvPy = Join-Path $backend ".venv\Scripts\python.exe"
Write-SetupPhase "가상환경 (backend\.venv)" "없을 때만 생성합니다."
if (-not (Test-Path $venvPy)) {
    Write-Host "가상환경 생성: backend\.venv" -ForegroundColor Yellow
    & $pythonExe -m venv (Join-Path $backend ".venv")
}
if (-not (Test-Path $venvPy)) {
    throw "가상환경 생성에 실패했습니다."
}
Write-SetupPhaseDone "가상환경"

$env:PIP_PROGRESS_BAR = "on"
Write-SetupPhase "pip: pip·wheel 업그레이드" "PIP_PROGRESS_BAR=on (지원되는 pip 에서 진행 표시)"
Write-Host "실행: pip install --upgrade pip wheel" -ForegroundColor DarkGray
& $venvPy -m pip install --upgrade pip wheel
Write-SetupPhaseDone "pip·wheel 업그레이드"

Write-SetupPhase "pip: requirements.txt" "백엔드 의존성(시간이 꽤 걸릴 수 있음)"
Write-Host "실행: pip install -r backend\requirements.txt" -ForegroundColor DarkGray
& $venvPy -m pip install -r (Join-Path $backend "requirements.txt")
Write-SetupPhaseDone "requirements.txt"

if (-not $SkipOcr) {
    Write-SetupPhase "pip: requirements-ocr.txt" "용량이 큰 OCR 패키지(수 분~)"
    Write-Host "실행: pip install -r backend\requirements-ocr.txt" -ForegroundColor DarkGray
    & $venvPy -m pip install -r (Join-Path $backend "requirements-ocr.txt")
    Write-SetupPhaseDone "requirements-ocr.txt"
} else {
    Write-Host "OCR 건너뜀 (-SkipOcr). 필요 시: pip install -r backend\requirements-ocr.txt" -ForegroundColor DarkYellow
}

Write-SetupPhase "NLTK 데이터" "RAKE 등. 보통 수 초~1분, 망에 따라 더 걸릴 수 있음. 패키지별 로그 출력."
# PS 5.1 + UTF-8 무BOM 저장소에서 python -c @" ... "@ 는 파서가 깨질 수 있어 임시 .py 로 실행
$nltkPy = Join-Path $env:TEMP ("job-assistant-nltk-{0}.py" -f [guid]::NewGuid().ToString("N"))
@(
    'import nltk',
    'for pkg in ("punkt", "punkt_tab", "stopwords"):',
    '    print("NLTK downloading:", pkg, flush=True)',
    '    try:',
    '        nltk.download(pkg, quiet=False)',
    '    except Exception as e:',
    '        print("NLTK error:", pkg, e, flush=True)'
) | Set-Content -LiteralPath $nltkPy -Encoding ASCII
try {
    & $venvPy $nltkPy
} finally {
    Remove-Item -LiteralPath $nltkPy -Force -ErrorAction SilentlyContinue
}
Write-SetupPhaseDone "NLTK 데이터"

$envExample = Join-Path $backend ".env.example"
$envFile = Join-Path $backend ".env"
Write-SetupPhase "backend\.env" ".env.example -> .env (없을 때만)"
if (-not (Test-Path $envFile) -and (Test-Path $envExample)) {
    Copy-Item $envExample $envFile
    Write-Host "backend\.env 생성 (.env.example 복사)" -ForegroundColor Green
} elseif (Test-Path $envFile) {
    Write-Host "backend\.env 이미 있음 — 덮어쓰지 않음" -ForegroundColor DarkGray
}
Write-SetupPhaseDone "backend\.env"

if (-not $SkipOllama) {
    Write-SetupPhase "Ollama (선택)" "winget 설치 시도 후 모델 pull (용량·시간 큼)"
    Refresh-SessionPath
    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $ollama) {
        $winget = Get-Command winget -ErrorAction SilentlyContinue
        if ($winget) {
            Write-Host "Ollama winget 설치 시도..." -ForegroundColor Yellow
            $prev = $ErrorActionPreference
            $ErrorActionPreference = "SilentlyContinue"
            try {
                & winget install -e --id Ollama.Ollama --accept-package-agreements --accept-source-agreements 2>&1 | Out-Host
            } catch {
                Write-Warning "winget으로 Ollama 설치 실패: $_ 수동 설치: https://ollama.com/download"
            } finally {
                $ErrorActionPreference = $prev
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
            & ollama pull $model 2>&1 | Out-Host
        } catch {
            Write-Warning "ollama pull 실패. Ollama 앱을 실행한 뒤 터미널에서: ollama pull $model"
        }
    } else {
        Write-Warning "ollama 명령을 찾을 수 없습니다. 설치 후 새 터미널에서 ollama serve / pull 을 실행하세요."
    }
    Write-SetupPhaseDone "Ollama"
} else {
    Write-Host "Ollama 건너뜀 (-SkipOllama)" -ForegroundColor DarkYellow
}

if (-not $SkipFrontend) {
    Write-SetupPhase "Node.js / 프론트" "winget 으로 Node LTS 시도(옵션), npm install"
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
                Write-Host "npm install (frontend) ... 로그 레벨 info" -ForegroundColor Yellow
                npm install --loglevel info
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
    Write-SetupPhaseDone "Node.js / 프론트"
}

Write-Host ""
Write-Host "설치 완료." -ForegroundColor Green
Write-Host "  백엔드: cd backend; .\.venv\Scripts\activate; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
Write-Host "  프론트: cd frontend; npm run dev"
Write-Host "  API 문서: http://127.0.0.1:8000/docs"
Write-Host "자세한 사용법은 README.md 를 참고하세요."
