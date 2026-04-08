"""
ReadMate 공통 설정.
환경변수(.env)를 로드하고, 경로·모델명·임계값 등 전역 상수를 정의한다.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pyprojroot import here

# ─────────────────────────────────────────
# 프로젝트 루트 & .env 로드
# ─────────────────────────────────────────

ROOT: Path = here()
load_dotenv(ROOT / '.env')

from lib.utils.path import (
    data_path,
    embeddings_path,
    model_path,
    static_tts_path,
    tmp_path,
    voices_path,
)

# ─────────────────────────────────────────
# 경로
# ─────────────────────────────────────────

DATA_DIR: Path = data_path()
MODEL_DIR: Path = model_path()
TMP_DIR: Path = tmp_path()
VOICES_DIR: Path = voices_path()
EMBEDDINGS_DIR: Path = embeddings_path()
STATIC_TTS_DIR: Path = static_tts_path()
STATIC_TTS_MANIFEST: Path = static_tts_path('manifest.json')

# ─────────────────────────────────────────
# API 키
# ─────────────────────────────────────────

CLOVA_API_KEY: str = os.getenv('CLOVA_API_KEY', '')
CLOVA_API_URL: str = os.getenv('CLOVA_API_URL', '')
OPENAI_API_KEY: str = os.getenv('OPENAI_API_KEY', '')
ELEVENLABS_API_KEY: str = os.getenv('ELEVENLABS_API_KEY', '')

# ─────────────────────────────────────────
# 모델명
# ─────────────────────────────────────────

LLM_ENGINE: str = os.getenv('LLM_ENGINE', 'gemma')  # gemma | qwen | openai
LLM_SERVER_URL: str = os.getenv('LLM_SERVER_URL', 'http://localhost:8000')
LLM_MODEL_DEFAULT: str = 'google/gemma-4-E4B-it'
LLM_MODEL_LARGE: str = 'google/gemma-4-26B-A4B-it'
LLM_MODEL_API: str = 'gpt-4.1-mini'

STT_MODEL: str = 'large-v3'  # faster-whisper 모델 크기

TTS_MODEL: str = 'tts_models/multilingual/multi-dataset/xtts_v2'
ZONOS_MODEL: str = 'Zyphra/Zonos-v0.1-transformer'

# ─────────────────────────────────────────
# 파이프라인 임계값
# ─────────────────────────────────────────

POPPLER_PATH: str = os.getenv('POPPLER_PATH', r'C:\Release-25.12.0-0\poppler-25.12.0\Library\bin')

OCR_CONFIDENCE_THRESHOLD: float = 0.75  # 이 값 미만이면 폴백 검토
PDF_MIN_CHARS: int = 100  # 이 값 미만이면 스캔형으로 판별
LLM_MAX_RETRIES: int = 3
LLM_MAX_INPUT_CHARS: int = 12000
LLM_MAX_NEW_TOKENS: int = 768
