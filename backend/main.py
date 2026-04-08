"""
ReadMate LLM 서버 진입점.

실행:
    uv run python -m backend.main          # prod (기본)
    uv run python -m backend.main --dev    # dev (Edge TTS 사용)

환경변수:
    LLM_ENGINE  gemma (기본) | qwen | openai
    APP_ENV     prod (기본) | dev
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.llm_factory import create_llm
from api.routes import http as http_routes
from api.routes import tts as tts_routes
from api.routes import websocket as ws_routes
from services.llm_gemma import GemmaLLM

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """서버 시작 시 LLM 모델을 로드하고, 종료 시 정리한다."""
    logger.info('[startup] LLM 모델 로드 시작')
    app.state.llm = create_llm()
    logger.info('[startup] LLM 모델 로드 완료')
    logger.info('[startup] 퀴즈 전용 Gemma4 LLM 로드 시작')
    app.state.quiz_llm = GemmaLLM()  # 퀴즈는 항상 Gemma4 사용 (클래스 공유 모델 재사용)
    logger.info('[startup] 퀴즈 전용 Gemma4 LLM 로드 완료')
    yield
    logger.info('[shutdown] 서버 종료')


app = FastAPI(
    title='ReadMate LLM Server',
    description='텍스트 요약·정리·질의응답 API (HTTP + WebSocket)',
    version='0.1.0',
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

@app.middleware('http')
async def log_requests(request, call_next):
    logger.info(f'[http] {request.method} {request.url.path}')
    response = await call_next(request)
    logger.info(f'[http] {request.method} {request.url.path} - {response.status_code}')
    return response

app.include_router(tts_routes.router)
app.include_router(http_routes.router)
app.include_router(ws_routes.router)


@app.get('/health')
def health() -> dict[str, str]:
    """서버 상태 확인."""
    return {'status': 'ok'}


if __name__ == '__main__':
    import argparse
    import os

    import uvicorn

    parser = argparse.ArgumentParser(description='ReadMate 서버 실행')
    parser.add_argument('--dev', action='store_true', help='dev 모드 (Edge TTS 사용)')
    parser.add_argument('--port', type=int, default=28765, help='서버 포트 (기본: 28765)')
    args = parser.parse_args()

    if args.dev:
        os.environ['APP_ENV'] = 'dev'
        logger.info('[startup] dev 모드로 실행합니다 (TTS: Edge TTS)')
    else:
        logger.info('[startup] prod 모드로 실행합니다')

    uvicorn.run('backend.main:app', host='0.0.0.0', port=args.port, reload=True)
