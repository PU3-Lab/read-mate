"""
ReadMate LLM 서버 진입점.

실행:
    uv run uvicorn backend.main:app --reload --port 8000

환경변수:
    LLM_ENGINE  gemma (기본) | qwen | openai
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from api.llm_factory import get_llm
from api.routes.http import router as http_router
from api.routes.websocket import router as ws_router

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """서버 시작 시 LLM 모델을 로드하고, 종료 시 정리한다."""
    logger.info('[startup] LLM 모델 로드 시작')
    get_llm()
    logger.info('[startup] LLM 모델 로드 완료')
    yield
    logger.info('[shutdown] 서버 종료')


app = FastAPI(
    title='ReadMate LLM Server',
    description='텍스트 요약·정리·질의응답 API (HTTP + WebSocket)',
    version='0.1.0',
    lifespan=lifespan,
)

app.include_router(http_router)
app.include_router(ws_router)


@app.get('/health')
def health() -> dict[str, str]:
    """서버 상태 확인."""
    return {'status': 'ok'}
