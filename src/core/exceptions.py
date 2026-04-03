"""ReadMate 사용자 정의 예외 클래스."""

from __future__ import annotations


class ReadMateError(Exception):
    """ReadMate 최상위 예외. 모든 커스텀 예외의 베이스."""


class InputValidationError(ReadMateError):
    """지원하지 않는 파일 형식 또는 빈 입력."""


class OCRQualityError(ReadMateError):
    """OCR 결과 품질이 기준 미달."""


class PDFExtractionError(ReadMateError):
    """PDF 텍스트 추출 실패."""


class STTError(ReadMateError):
    """음성-텍스트 변환 실패."""


class LLMGenerationError(ReadMateError):
    """LLM 생성 실패 (재시도 초과 포함)."""


class TTSGenerationError(ReadMateError):
    """TTS 음성 합성 실패."""


class PipelineExecutionError(ReadMateError):
    """파이프라인 실행 중 복구 불가능한 오류."""
