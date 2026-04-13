#!/usr/bin/env bash
# Find My Job Insight — macOS/Linux 초기 환경 (Python, OCR, 프론트, Ollama 선택)
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

echo "=== Find My Job Insight — 로컬 설치 ==="
echo "저장소: $REPO_ROOT"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "Python 3가 필요합니다." >&2
  exit 1
fi

BACKEND="$REPO_ROOT/backend"
VENV_PY="$BACKEND/.venv/bin/python"
if [[ ! -x "$VENV_PY" ]]; then
  echo "가상환경 생성: backend/.venv"
  "$PY" -m venv "$BACKEND/.venv"
  VENV_PY="$BACKEND/.venv/bin/python"
fi

echo "pip 및 requirements 설치..."
"$VENV_PY" -m pip install --upgrade pip wheel
"$VENV_PY" -m pip install -r "$BACKEND/requirements.txt"
if [[ "$SKIP_OCR" -eq 0 ]]; then
  echo "OCR 의존성 설치..."
  "$VENV_PY" -m pip install -r "$BACKEND/requirements-ocr.txt"
else
  echo "OCR 건너뜀. 필요 시: pip install -r backend/requirements-ocr.txt"
fi

"$VENV_PY" -c "import nltk
for pkg in ('punkt', 'punkt_tab', 'stopwords'):
    try:
        nltk.download(pkg, quiet=True)
    except Exception as e:
        print('nltk', pkg, e)
"

if [[ ! -f "$BACKEND/.env" && -f "$BACKEND/.env.example" ]]; then
  cp "$BACKEND/.env.example" "$BACKEND/.env"
  echo "backend/.env 생성"
fi

if [[ "$SKIP_OLLAMA" -eq 0 ]]; then
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
else
  echo "Ollama 건너뜀 (--skip-ollama)"
fi

if [[ "$SKIP_FRONTEND" -eq 0 ]]; then
  if command -v npm >/dev/null 2>&1; then
    FE="$REPO_ROOT/frontend"
    if [[ ! -d "$FE/node_modules" ]]; then
      (cd "$FE" && npm install)
    fi
    if [[ ! -f "$FE/.env.local" && -f "$FE/.env.local.example" ]]; then
      cp "$FE/.env.local.example" "$FE/.env.local"
      echo "frontend/.env.local 생성"
    fi
  else
    echo "Node/npm 없음 — Node LTS 설치 후 frontend에서 npm install 하세요."
  fi
fi

echo ""
echo "설치 완료."
echo "  백엔드: cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
echo "  프론트: cd frontend && npm run dev"
echo "자세한 내용은 README.md 참고."
