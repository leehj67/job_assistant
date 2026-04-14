#!/usr/bin/env bash
# 일햇음청년 제조기 — macOS/Linux 초기 환경 (Python, OCR, 프론트, Ollama 선택)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SKIP_OLLAMA=0
SKIP_OCR=0
SKIP_FRONTEND=0
for arg in "$@"; do
  case "$arg" in
    --skip-ollama) SKIP_OLLAMA=1 ;;
    --skip-ocr) SKIP_OCR=1 ;;
    --skip-frontend) SKIP_FRONTEND=1 ;;
  esac
done

log_phase() {
  echo ""
  echo "------------------------------------------------------------"
  echo "[$(date +%H:%M:%S)]  $1"
  if [[ -n "${2:-}" ]]; then
    echo "       $2"
  fi
  echo "------------------------------------------------------------"
}

log_done() {
  echo "[$(date +%H:%M:%S)]  완료: $1"
}

echo "=== 일햇음청년 제조기 — 로컬 설치 ==="
echo "저장소: $REPO_ROOT"

log_phase "Python 확인" "python3 또는 python 이 PATH 에 있어야 합니다."
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "Python 3가 필요합니다." >&2
  exit 1
fi
log_done "Python 확인"

BACKEND="$REPO_ROOT/backend"
VENV_PY="$BACKEND/.venv/bin/python"
log_phase "가상환경 (backend/.venv)" "없을 때만 생성"
if [[ ! -x "$VENV_PY" ]]; then
  echo "가상환경 생성: backend/.venv"
  "$PY" -m venv "$BACKEND/.venv"
  VENV_PY="$BACKEND/.venv/bin/python"
fi
log_done "가상환경"

export PIP_PROGRESS_BAR=on

log_phase "pip: pip·wheel 업그레이드" "PIP_PROGRESS_BAR=on (지원 pip)"
echo "실행: pip install --upgrade pip wheel"
"$VENV_PY" -m pip install --upgrade pip wheel
log_done "pip·wheel 업그레이드"

log_phase "pip: requirements.txt" "백엔드 의존성(시간이 걸릴 수 있음)"
echo "실행: pip install -r backend/requirements.txt"
"$VENV_PY" -m pip install -r "$BACKEND/requirements.txt"
log_done "requirements.txt"

if [[ "$SKIP_OCR" -eq 0 ]]; then
  log_phase "pip: requirements-ocr.txt" "용량이 큰 OCR 패키지"
  echo "실행: pip install -r backend/requirements-ocr.txt"
  "$VENV_PY" -m pip install -r "$BACKEND/requirements-ocr.txt"
  log_done "requirements-ocr.txt"
else
  echo "OCR 건너뜀. 필요 시: pip install -r backend/requirements-ocr.txt"
fi

NLTK_PY="$(mktemp "${TMPDIR:-/tmp}/job-assistant-nltk.XXXXXX")"
trap 'rm -f "$NLTK_PY"' EXIT
cat >"$NLTK_PY" <<'PY'
import nltk
for pkg in ("punkt", "punkt_tab", "stopwords"):
    print("NLTK downloading:", pkg, flush=True)
    try:
        nltk.download(pkg, quiet=False)
    except Exception as e:
        print("NLTK error:", pkg, e, flush=True)
PY
log_phase "NLTK 데이터" "인터넷 필요. 패키지별 로그 출력."
"$VENV_PY" "$NLTK_PY"
log_done "NLTK 데이터"

log_phase "backend/.env" ".env.example -> .env (없을 때만)"
if [[ ! -f "$BACKEND/.env" && -f "$BACKEND/.env.example" ]]; then
  cp "$BACKEND/.env.example" "$BACKEND/.env"
  echo "backend/.env 생성"
fi
log_done "backend/.env"

if [[ "$SKIP_OLLAMA" -eq 0 ]]; then
  log_phase "Ollama (선택)" "brew 또는 수동 안내 후 pull"
  if ! command -v ollama >/dev/null 2>&1; then
    if command -v brew >/dev/null 2>&1; then
      echo "Homebrew로 Ollama 설치 시도..."
      brew install ollama || true
    else
      echo "Ollama 미설치 — https://ollama.com/download 또는 curl:"
      echo "  curl -fsSL https://ollama.com/install.sh | sh"
    fi
  fi
  if command -v ollama >/dev/null 2>&1; then
    echo "Ollama 모델 pull: llama3:latest"
    ollama pull llama3:latest || echo "ollama pull 실패 시 ollama serve 실행 후 재시도하세요."
  fi
  log_done "Ollama"
else
  echo "Ollama 건너뜀 (--skip-ollama)"
fi

if [[ "$SKIP_FRONTEND" -eq 0 ]]; then
  log_phase "Node.js / 프론트" "npm install --loglevel info"
  if command -v npm >/dev/null 2>&1; then
    FE="$REPO_ROOT/frontend"
    if [[ ! -d "$FE/node_modules" ]]; then
      (cd "$FE" && npm install --loglevel info)
    fi
    if [[ ! -f "$FE/.env.local" && -f "$FE/.env.local.example" ]]; then
      cp "$FE/.env.local.example" "$FE/.env.local"
      echo "frontend/.env.local 생성"
    fi
  else
    echo "Node/npm 없음 — Node LTS 설치 후 frontend에서 npm install 하세요."
  fi
  log_done "Node.js / 프론트"
fi

echo ""
echo "설치 완료."
echo "  백엔드: cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
echo "  프론트: cd frontend && npm run dev"
echo "자세한 내용은 README.md 참고."
