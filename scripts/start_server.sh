#!/usr/bin/env bash
# ReadMate LLM 서버 실행 스크립트 (macOS / Linux)
#
# 사용법:
#   ./scripts/start_server.sh
#   ./scripts/start_server.sh --port 8080
#   LLM_ENGINE=openai ./scripts/start_server.sh

set -e

PORT=${PORT:-8000}

# --port 인자 파싱
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    *) shift ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "ReadMate LLM 서버 시작"
echo "  포트    : $PORT"
echo "  엔진    : ${LLM_ENGINE:-openai (기본)}"
echo "  주소    : http://localhost:$PORT"
echo ""

uv run uvicorn backend.main:app --host 0.0.0.0 --port "$PORT" --reload
