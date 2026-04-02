"""
ReadMate 공통 설정.
환경변수(.env)를 로드하고, 경로·모델명·임계값 등 전역 상수를 정의한다.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from pyprojroot import here

# ─────────────────────────────────────────
# 프로젝트 루트 & .env 로드
# ─────────────────────────────────────────

ROOT: Path = here()
load_dotenv(ROOT / '.env')

# ─────────────────────────────────────────
# 경로
# ─────────────────────────────────────────

DATA_DIR: Path = ROOT / 'data'
MODEL_DIR: Path = DATA_DIR / 'models'
TMP_DIR: Path = Path(tempfile.gettempdir()) / 'readmate'
TTS_VOICE_DIR: Path = DATA_DIR / 'audio' / 'voices'
ZONOS_EMBEDDINGS_DIR: Path = TTS_VOICE_DIR / 'zonos'

for _dir in (DATA_DIR, MODEL_DIR, TMP_DIR, TTS_VOICE_DIR, ZONOS_EMBEDDINGS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

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

LLM_MODEL_DEFAULT: str = 'Qwen/Qwen2.5-7B-Instruct'
LLM_MODEL_LARGE: str = 'Qwen/Qwen2.5-14B-Instruct'
LLM_MODEL_API: str = 'gpt-4.1-mini'

STT_MODEL: str = 'large-v3'  # faster-whisper 모델 크기

TTS_MODEL: str = 'hexgrad/Kokoro-82M'  # kokoro-onnx HuggingFace repo
ZONOS_MODEL: str = 'Zyphra/Zonos-v0.1-transformer'
ZONOS_LANGUAGE: str = os.getenv('ZONOS_LANGUAGE', 'ko')
ZONOS_MAX_NEW_TOKENS: int = 86 * 30
ZONOS_CFG_SCALE: float = float(os.getenv('ZONOS_CFG_SCALE', '1.7'))
ZONOS_MIN_P: float = float(os.getenv('ZONOS_MIN_P', '0.08'))
ZONOS_SPEAKING_RATE: float = float(os.getenv('ZONOS_SPEAKING_RATE', '10.0'))
ZONOS_PITCH_STD: float = float(os.getenv('ZONOS_PITCH_STD', '18.0'))
ZONOS_DNSMOS_OVRL: float = float(os.getenv('ZONOS_DNSMOS_OVRL', '4.0'))

# ─────────────────────────────────────────
# 파이프라인 임계값
# ─────────────────────────────────────────

OCR_CONFIDENCE_THRESHOLD: float = 0.75  # 이 값 미만이면 폴백 검토
PDF_MIN_CHARS: int = 100  # 이 값 미만이면 스캔형으로 판별
LLM_MAX_RETRIES: int = 3
LLM_MAX_INPUT_CHARS: int = 12000
LLM_MAX_NEW_TOKENS: int = 768
