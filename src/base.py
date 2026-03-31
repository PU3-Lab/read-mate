"""파이프라인 인터페이스 — 모델 교체 가능한 ABC 정의."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np


class BaseOCR(ABC):
    """OCR 엔진 인터페이스."""

    @abstractmethod
    def extract(self, image: np.ndarray) -> str:
        """이미지에서 텍스트 추출.

        Args:
            image: 전처리된 numpy array

        Returns:
            추출된 텍스트 문자열
        """


class BaseLLM(ABC):
    """LLM 분석 인터페이스."""

    @abstractmethod
    def analyze(self, text: str) -> dict:
        """텍스트 분석 후 JSON 반환.

        Args:
            text: OCR 추출 텍스트

        Returns:
            {
                "summary": str,
                "quiz": [{"question": str, "options": list, "answer": int}],
                "keywords": list[str],
                "simple_explanation": str
            }
        """


class BaseTTS(ABC):
    """TTS 합성 인터페이스."""

    @abstractmethod
    def synthesize(self, text: str) -> Path:
        """텍스트를 음성 파일로 합성.

        Args:
            text: 합성할 텍스트

        Returns:
            생성된 .wav 파일 경로
        """
