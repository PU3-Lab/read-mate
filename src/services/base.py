"""
ReadMate 서비스 ABC 베이스 클래스.
각 모델 엔진은 이 인터페이스를 구현한다.
모델 교체 시 베이스 클래스만 맞추면 파이프라인 변경 없이 스왑 가능.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from models.schemas import (
    LLMResult,
    OCRResult,
    PDFResult,
    QuizEvalResult,
    STTResult,
    TaskType,
    TTSResult,
)


class BaseOCR(ABC):
    """OCR 엔진 인터페이스."""

    @abstractmethod
    def recognize(self, image_bytes: bytes) -> OCRResult:
        """
        이미지 바이트를 받아 OCR 결과 반환.

        Args:
            image_bytes: 이미지 원본 바이트

        Returns:
            OCRResult: 박스 목록, 엔진명, 평균 confidence, 원문 텍스트
        """
        ...


class BasePDF(ABC):
    """PDF 추출 엔진 인터페이스."""

    @abstractmethod
    def extract(self, pdf_bytes: bytes) -> PDFResult:
        """
        PDF 바이트를 받아 텍스트 추출 결과 반환.
        스캔형 판별 후 is_scanned 플래그로 OCR 분기 여부를 알린다.

        Args:
            pdf_bytes: PDF 원본 바이트

        Returns:
            PDFResult: 추출 텍스트, 페이지 수, 스캔형 여부
        """
        ...


class BaseSTT(ABC):
    """STT 엔진 인터페이스."""

    @abstractmethod
    def transcribe(self, audio_bytes: bytes) -> STTResult:
        """
        오디오 바이트를 받아 STT 결과 반환.

        Args:
            audio_bytes: 오디오 원본 바이트

        Returns:
            STTResult: 전체 텍스트, 언어, 세그먼트 목록, 엔진명
        """
        ...


class BaseLLM(ABC):
    """LLM 엔진 인터페이스. 구현체는 llm_base.ChunkedLLM을 상속한다."""

    @abstractmethod
    def generate(
        self, text: str, task: TaskType, question: str | None = None
    ) -> LLMResult:
        """
        텍스트와 태스크 타입을 받아 LLM 결과 반환.

        Args:
            text: 분석할 원문 텍스트
            task: SUMMARIZE | QA | QUIZ
            question: QA 태스크일 때 사용자 질문

        Returns:
            LLMResult: 요약, 핵심 정리, 질의응답 답변 등
        """
        ...

    @abstractmethod
    def evaluate_answer(
        self,
        question: str,
        options: list[str],
        correct_index: int,
        user_answer: str,
    ) -> QuizEvalResult:
        """
        사용자의 음성 답변을 채점하고 이유를 설명한다.

        Args:
            question: 퀴즈 문제 텍스트
            options: 보기 목록
            correct_index: 정답 인덱스 (0-based)
            user_answer: 사용자 음성 인식 텍스트

        Returns:
            QuizEvalResult: 정오 여부, 설명
        """
        ...


class BaseTTS(ABC):
    """TTS 엔진 인터페이스."""

    @abstractmethod
    def synthesize(self, text: str, voice_preset: str = 'default') -> TTSResult:
        """
        텍스트를 음성으로 합성해 WAV 파일 경로 반환.

        Args:
            text: 읽어줄 텍스트
            voice_preset: 프리셋 목소리 이름

        Returns:
            TTSResult: 오디오 파일 경로, 목소리, 엔진명, 재생 시간
        """
        ...

    @abstractmethod
    def list_presets(self) -> list[str]:
        """사용 가능한 프리셋 목소리 목록 반환."""
        ...
