#!/usr/bin/env bash
# 일햇음청년 제조기 — setup.sh 후 백엔드·프론트 동시 기동 (macOS/Linux)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKIP_SETUP=0
SETUP_ARGS=()
for a in "$@"; do
  case "$a" in
    --skip-setup) SKIP_SETUP=1 ;;
    *) SETUP_ARGS+=("$a") ;;
  esac
done

kill_port() {
  local port=$1
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti:"$port" 2>/dev/null | xargs kill -9 2>/dev/null || true
  fi
}

echo "=== 일햇음청년 제조기 — 설치 및 로컬 실행 ==="
echo "저장소: $ROOT"

if [[ "$SKIP_SETUP" -ne 1 ]]; then
  "$ROOT/scripts/setup.sh" "${SETUP_ARGS[@]}"
else
  echo "(setup 생략: --skip-setup)"
fi

kill_port 8000
kill_port 3000
sleep 1

BE_PY="$ROOT/backend/.venv/bin/python"
if [[ ! -x "$BE_PY" ]]; then
  echo "backend/.venv 이 없습니다. --skip-setup 없이 다시 실행하세요." >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "npm 이 필요합니다. Node LTS를 설치하세요." >&2
  exit 1
fi

BE_PID=""
FE_PID=""
cleanup() {
  if [[ -n "${BE_PID:-}" ]]; then kill "$BE_PID" 2>/dev/null || true; fi
  if [[ -n "${FE_PID:-}" ]]; then kill "$FE_PID" 2>/dev/null || true; fi
  kill_port 8000
  kill_port 3000
}
trap 'echo ""; echo "종료 중..."; cleanup; exit 130' INT TERM

export PYTHONPATH="$ROOT/backend"
(
  cd "$ROOT/backend"
  "$BE_PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
) &
BE_PID=$!

(
  cd "$ROOT/frontend"
  npm run dev
) &
FE_PID=$!

echo ""
echo "백엔드 PID $BE_PID | 프론트 PID $FE_PID"
echo "  API 문서: http://127.0.0.1:8000/docs"
echo "  웹 UI:   http://localhost:3000"
echo "종료: 이 터미널에서 Ctrl+C"
wait
