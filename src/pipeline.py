"""파이프라인 팩토리 — 모델 교체 진입점."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

from src.base import BaseOCR, BaseLLM, BaseTTS

load_dotenv()


class Pipeline:
    """OCR → LLM → TTS 파이프라인.

    모델 교체는 생성자에 원하는 구현체를 주입하면 됨.

    Examples:
        # 기본: 전체 로컬
        pipeline = Pipeline.local()

        # OCR만 API로 교체
        pipeline = Pipeline.local(ocr=ClovaOCR(api_key='...'))

        # 전체 API
        pipeline = Pipeline.api()
    """

    def __init__(self, ocr: BaseOCR, llm: BaseLLM, tts: BaseTTS):
        self.ocr = ocr
        self.llm = llm
        self.tts = tts

    def run(self, image: np.ndarray) -> dict:
        """이미지 → 분석 결과 + 음성 파일 경로 반환.

        Args:
            image: 전처리된 numpy array

        Returns:
            {
                "ocr_text": str,
                "summary": str,
                "quiz": list,
                "keywords": list,
                "simple_explanation": str,
                "audio_path": Path
            }
        """
        ocr_text = self.ocr.extract(image)
        llm_result = self.llm.analyze(ocr_text)
        audio_path = self.tts.synthesize(llm_result['summary'])

        return {
            'ocr_text': ocr_text,
            **llm_result,
            'audio_path': audio_path,
        }

    # ── 팩토리 메서드 ─────────────────────────────────────────────────────────

    @classmethod
    def local(
        cls,
        ocr: BaseOCR | None = None,
        llm: BaseLLM | None = None,
        tts: BaseTTS | None = None,
    ) -> 'Pipeline':
        """로컬 모델 기반 파이프라인 (기본값).

        특정 모듈만 교체하고 싶으면 해당 인자에 구현체 주입.
        """
        from src.ocr import PaddleOCREngine
        from src.llm import QwenLLM
        from src.tts import XTTSEngine

        return cls(
            ocr=ocr or PaddleOCREngine(),
            llm=llm or QwenLLM(),
            tts=tts or XTTSEngine(),
        )

    @classmethod
    def api(
        cls,
        ocr: BaseOCR | None = None,
        llm: BaseLLM | None = None,
        tts: BaseTTS | None = None,
    ) -> 'Pipeline':
        """API 기반 파이프라인 (성능 미달 시 폴백).

        .env에서 API 키를 읽어옴:
            CLOVA_API_KEY, OPENAI_API_KEY, ELEVENLABS_API_KEY
        """
        from src.ocr import ClovaOCR
        from src.llm import OpenAILLM
        from src.tts import ElevenLabsTTS

        return cls(
            ocr=ocr or ClovaOCR(api_key=os.environ['CLOVA_API_KEY']),
            llm=llm or OpenAILLM(api_key=os.environ['OPENAI_API_KEY']),
            tts=tts or ElevenLabsTTS(api_key=os.environ['ELEVENLABS_API_KEY']),
        )
