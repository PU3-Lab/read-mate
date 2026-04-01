"""
ReadMate 파이프라인 전체 입출력 데이터 계약 정의.
단계 간 전달되는 모든 데이터 타입은 여기서 관리한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# ─────────────────────────────────────────
# Enum
# ─────────────────────────────────────────


class InputType(Enum):
    IMAGE = 'image'
    PDF = 'pdf'
    HWP = 'hwp'
    AUDIO = 'audio'
    QUESTION = 'question'


class TaskType(Enum):
    SUMMARIZE = 'summarize'
    QA = 'qa'


class PipelineStatus(Enum):
    IDLE = 'idle'
    RUNNING = 'running'
    SUCCESS = 'success'
    FAILED = 'failed'


# ─────────────────────────────────────────
# 입력
# ─────────────────────────────────────────


@dataclass
class InputPayload:
    """파이프라인 진입점 입력 데이터."""

    input_type: InputType
    file_name: str
    content: bytes
    question: str | None = None  # 질의응답용 질문 텍스트
    voice_preset: str = 'default'  # TTS 목소리 프리셋


# ─────────────────────────────────────────
# OCR
# ─────────────────────────────────────────


@dataclass
class OCRBox:
    """OCR 박스 단위 결과."""

    text: str
    confidence: float
    bbox: list[list[int]]
    source: str  # 'paddle' | 'clova'


@dataclass
class OCRResult:
    """OCR 서비스 전체 결과."""

    boxes: list[OCRBox]
    engine: str
    avg_confidence: float
    raw_text: str


# ─────────────────────────────────────────
# PDF
# ─────────────────────────────────────────


@dataclass
class PDFResult:
    """PDF 추출 결과."""

    text: str
    page_count: int
    is_scanned: bool  # True면 OCR 경로를 통해 추출된 것


# ─────────────────────────────────────────
# HWP
# ─────────────────────────────────────────


@dataclass
class HWPResult:
    """HWP 추출 결과."""

    text: str
    page_count: int
    is_image_based: bool  # True면 LibreOffice + OCR 경로로 처리된 것
    extraction_method: str  # 'pyhwp' | 'libreoffice_pdf' | 'libreoffice_ocr'


# ─────────────────────────────────────────
# STT
# ─────────────────────────────────────────


@dataclass
class STTSegment:
    """STT 세그먼트 단위 결과."""

    start: float
    end: float
    text: str


@dataclass
class STTResult:
    """STT 서비스 전체 결과."""

    text: str
    language: str
    segments: list[STTSegment]
    engine: str


# ─────────────────────────────────────────
# LLM
# ─────────────────────────────────────────


@dataclass
class QuizItem:
    """퀴즈 문항."""

    question: str
    options: list[str]
    answer_index: int


@dataclass
class LLMResult:
    """LLM 서비스 결과."""

    summary: str
    key_points: list[str]
    qa_answer: str | None = None
    quiz: list[QuizItem] | None = None
    engine: str = ''


# ─────────────────────────────────────────
# TTS
# ─────────────────────────────────────────


@dataclass
class TTSResult:
    """TTS 서비스 결과."""

    audio_path: str
    voice_preset: str
    engine: str
    duration_sec: float


# ─────────────────────────────────────────
# 최종 파이프라인 결과
# ─────────────────────────────────────────


@dataclass
class PipelineResult:
    """파이프라인 최종 출력."""

    extracted_text: str
    llm_result: LLMResult | None = None
    tts_result: TTSResult | None = None
    ocr_engine: str | None = None
    stt_engine: str | None = None
    status: PipelineStatus = PipelineStatus.SUCCESS
    warnings: list[str] = field(default_factory=list)
