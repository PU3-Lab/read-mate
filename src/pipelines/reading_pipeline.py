"""
ReadMate 메인 파이프라인 오케스트레이터.
입력 타입에 따라 OCR/PDF/STT 경로를 분기하고
LLM → TTS 순서로 실행한다.
각 서비스는 ABC 인터페이스로 주입받아 모델 교체가 자유롭다.
"""

from __future__ import annotations

import logging

from models.schemas import (
    InputPayload,
    InputType,
    LLMResult,
    PDFResult,
    PipelineResult,
    PipelineStatus,
    STTResult,
    TaskType,
    TTSResult,
)
from services.base import BaseLLM, BaseOCR, BasePDF, BaseSTT, BaseTTS

logger = logging.getLogger(__name__)


class ReadingPipeline:
    """
    ReadMate 전체 파이프라인 오케스트레이터.

    각 서비스는 생성자에서 주입받는다.
    모델 교체는 해당 ABC를 구현한 클래스를 바꿔 끼우기만 하면 된다.

    Example:
        pipeline = ReadingPipeline(
            ocr=PaddleOCREngine(),
            pdf=PyPDFEngine(ocr_fallback=PaddleOCREngine()),
            stt=FasterWhisperEngine(),
            llm=GemmaLLM(),
            tts=XTTSEngine(),
        )
        result = pipeline.run(payload)
    """

    def __init__(
        self,
        ocr: BaseOCR,
        pdf: BasePDF,
        stt: BaseSTT,
        llm: BaseLLM,
        tts: BaseTTS,
    ) -> None:
        self.ocr = ocr
        self.pdf = pdf
        self.stt = stt
        self.llm = llm
        self.tts = tts

    def run(self, payload: InputPayload) -> PipelineResult:
        """
        입력 타입에 따라 적절한 경로로 분기해 전체 파이프라인 실행.

        Args:
            payload: 파일 타입, 콘텐츠, 질문, 목소리 설정 포함

        Returns:
            PipelineResult: 추출 텍스트, LLM 결과, TTS 결과, 경고 목록
        """
        warnings: list[str] = []

        try:
            # ── 1. 텍스트 추출 ──────────────────────────────
            extracted_text, ocr_engine, stt_engine = self._extract_text(
                payload, warnings
            )

            if not extracted_text.strip():
                return PipelineResult(
                    extracted_text='',
                    status=PipelineStatus.FAILED,
                    warnings=['텍스트 추출 결과가 비어 있습니다.'],
                )

            # ── 2. LLM 분석 ─────────────────────────────────
            task = TaskType.QA if payload.question else TaskType.SUMMARIZE
            llm_result = self._run_llm(extracted_text, task, payload.question, warnings)

            # ── 3. TTS 합성 ─────────────────────────────────
            tts_input = self._build_tts_input(llm_result, payload.question)
            tts_result = self._run_tts(tts_input, payload.voice_preset, warnings)

            return PipelineResult(
                extracted_text=extracted_text,
                llm_result=llm_result,
                tts_result=tts_result,
                ocr_engine=ocr_engine,
                stt_engine=stt_engine,
                status=PipelineStatus.SUCCESS,
                warnings=warnings,
            )

        except Exception as e:
            logger.exception('Pipeline execution failed')
            return PipelineResult(
                extracted_text='',
                status=PipelineStatus.FAILED,
                warnings=[f'파이프라인 오류: {e}'],
            )

    # ─────────────────────────────────────────────────────────
    # 텍스트 추출 분기
    # ─────────────────────────────────────────────────────────

    def _extract_text(
        self,
        payload: InputPayload,
        warnings: list[str],
    ) -> tuple[str, str | None, str | None]:
        """
        입력 타입에 따라 OCR / PDF / STT 경로로 분기.

        Returns:
            (추출 텍스트, ocr_engine, stt_engine)
        """
        match payload.input_type:
            case InputType.IMAGE:
                return self._run_image(payload.content, warnings)
            case InputType.PDF:
                return self._run_pdf(payload.content, warnings)
            case InputType.AUDIO:
                return self._run_audio(payload.content, warnings)
            case InputType.QUESTION:
                # 질문만 있는 경우: 텍스트 추출 없이 QA로 진행
                return payload.question or '', None, None
            case _:
                raise ValueError(f'지원하지 않는 입력 타입: {payload.input_type}')

    def _run_image(
        self, content: bytes, warnings: list[str]
    ) -> tuple[str, str | None, str | None]:
        """이미지 → OCR 경로."""
        result = self.ocr.recognize(content)
        if result.avg_confidence < 0.75:
            warnings.append(
                f'OCR 품질 낮음 (avg_conf={result.avg_confidence:.2f}). '
                f'엔진: {result.engine}'
            )
        logger.info(
            '[ocr] engine=%s avg_conf=%.2f', result.engine, result.avg_confidence
        )
        return result.raw_text, result.engine, None

    def _run_pdf(
        self, content: bytes, warnings: list[str]
    ) -> tuple[str, str | None, str | None]:
        """PDF → pypdf 또는 OCR 분기 경로."""
        result: PDFResult = self.pdf.extract(content)
        engine = 'ocr(scanned)' if result.is_scanned else 'pypdf'
        if result.is_scanned:
            warnings.append('스캔형 PDF로 판별되어 OCR로 처리했습니다.')
        logger.info('[pdf] engine=%s pages=%d', engine, result.page_count)
        return result.text, engine, None

    def _run_audio(
        self, content: bytes, warnings: list[str]
    ) -> tuple[str, str | None, str | None]:
        """오디오 → STT 경로."""
        result: STTResult = self.stt.transcribe(content)
        logger.info('[stt] engine=%s lang=%s', result.engine, result.language)
        return result.text, None, result.engine

    # ─────────────────────────────────────────────────────────
    # LLM
    # ─────────────────────────────────────────────────────────

    def _run_llm(
        self,
        text: str,
        task: TaskType,
        question: str | None,
        warnings: list[str],
    ) -> LLMResult:
        """LLM 분석 실행."""
        result = self.llm.generate(text, task, question)
        logger.info('[llm] engine=%s task=%s', result.engine, task.value)
        return result

    # ─────────────────────────────────────────────────────────
    # TTS
    # ─────────────────────────────────────────────────────────

    def _build_tts_input(self, llm_result: LLMResult, question: str | None) -> str:
        """TTS에 넘길 텍스트 결정. QA면 답변, 아니면 요약문 사용."""
        if question and llm_result.qa_answer:
            return llm_result.qa_answer
        return llm_result.summary

    def _run_tts(
        self, text: str, voice_preset: str, warnings: list[str]
    ) -> TTSResult | None:
        """TTS 합성 실행. 실패해도 파이프라인 전체를 막지 않는다."""
        try:
            result = self.tts.synthesize(text, voice_preset)
            logger.info(
                '[tts] engine=%s voice=%s duration=%.2fs',
                result.engine,
                result.voice_preset,
                result.duration_sec,
            )
            return result
        except Exception as e:
            warnings.append(f'TTS 실패 (오디오 생략): {e}')
            logger.warning('[tts] failed: %s', e)
            return None
