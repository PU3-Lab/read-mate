"""
ReadMate LLM 서버 진입점.

실행:
    uv run uvicorn backend.main:app --reload --port 8000

환경변수:
    LLM_ENGINE  gemma (기본) | qwen | openai
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# src 디렉터리를 모듈 탐색 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))

from fastapi import FastAPI

from api.routes.http import router as http_router
from api.routes.websocket import router as ws_router

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)

app = FastAPI(
    title='ReadMate LLM Server',
    description='텍스트 요약·정리·질의응답 API (HTTP + WebSocket)',
    version='0.1.0',
)

app.include_router(http_router)
app.include_router(ws_router)


@app.get('/health')
def health() -> dict[str, str]:
    """서버 상태 확인."""
    return {'status': 'ok'}
