#!/usr/bin/env bash
# ReadMate 서버 + Streamlit 동시 실행 스크립트 (macOS / Linux)
#
# 사용법:
#   ./scripts/start.sh
#   ./scripts/start.sh --dev
#   ./scripts/start.sh --server-port 8080 --app-port 8502
#   ./scripts/start.sh --dev --server-port 8080 --app-port 8502
#   LLM_ENGINE=openai ./scripts/start.sh

SERVER_PORT=${SERVER_PORT:-8000}
APP_PORT=${APP_PORT:-8501}
DEV_FLAG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --server-port) SERVER_PORT="$2"; shift 2 ;;
    --app-port)    APP_PORT="$2";    shift 2 ;;
    --dev)         DEV_FLAG="--dev"; shift ;;
    *) shift ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

SERVER_CMD="cd '$PROJECT_ROOT' && uv run python -m backend.main $DEV_FLAG --port $SERVER_PORT"
APP_CMD="cd '$PROJECT_ROOT' && LLM_SERVER_URL=http://localhost:$SERVER_PORT uv run streamlit run frontend/app.py --server.port $APP_PORT"

echo "=========================================="
echo "  ReadMate 전체 시작"
echo "  LLM 서버 : http://localhost:$SERVER_PORT"
echo "  앱       : http://localhost:$APP_PORT"
echo "  엔진     : ${LLM_ENGINE:-openai (기본)}"
echo "  모드     : ${DEV_FLAG:+dev (Edge TTS)}${DEV_FLAG:-prod (ElevenLabs)}"
echo "=========================================="
echo ""

open_terminal() {
  local title="$1"
  local cmd="$2"

  if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS — Terminal.app
    osascript \
      -e 'tell application "Terminal"' \
      -e "  do script \"printf '\\\\033]0;$title\\\\007'; $cmd\"" \
      -e '  activate' \
      -e 'end tell'

  elif command -v gnome-terminal &>/dev/null; then
    gnome-terminal --title="$title" -- bash -c "$cmd; exec bash"

  elif command -v konsole &>/dev/null; then
    konsole --new-tab -p tabtitle="$title" -e bash -c "$cmd; exec bash" &

  elif command -v xterm &>/dev/null; then
    xterm -title "$title" -e bash -c "$cmd; exec bash" &

  else
    echo "지원되는 터미널 에뮬레이터를 찾을 수 없습니다."
    echo "수동 실행: $cmd"
    return 1
  fi
}

open_terminal "ReadMate · LLM Server :$SERVER_PORT" "$SERVER_CMD"
sleep 1
open_terminal "ReadMate · Streamlit :$APP_PORT" "$APP_CMD"

echo "두 터미널 창이 열렸습니다."
echo "  LLM 서버 : http://localhost:$SERVER_PORT"
echo "  앱       : http://localhost:$APP_PORT"
