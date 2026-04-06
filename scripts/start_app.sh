#!/usr/bin/env bash
# ReadMate Streamlit 앱 실행 스크립트 (macOS / Linux)
#
# 사용법:
#   ./scripts/start_app.sh
#   ./scripts/start_app.sh --port 8502
#   LLM_SERVER_URL=http://localhost:9000 ./scripts/start_app.sh

set -e

PORT=${PORT:-8501}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    *) shift ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "ReadMate Streamlit 앱 시작"
echo "  포트          : $PORT"
echo "  앱 주소       : http://localhost:$PORT"
echo "  LLM 서버 주소 : ${LLM_SERVER_URL:-http://localhost:8000}"
echo ""

uv run streamlit run scripts/app.py --server.port "$PORT"
