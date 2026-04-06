"""
ReadMate 메인 파이프라인 오케스트레이터.
입력 타입에 따라 OCR/PDF/STT 경로를 분기하고 LLM, TTS를 순서대로 실행한다.
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
    UI나 API는 이 객체 하나만 호출하면 된다.
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
        입력 타입에 따라 적절한 경로로 분기해 전체 파이프라인을 실행한다.

        Args:
            payload: 입력 파일 정보, 질문, 음성 프리셋을 포함한 요청 데이터

        Returns:
            PipelineResult: 추출 텍스트, LLM 결과, TTS 결과, 경고 목록
        """
        warnings: list[str] = []

        try:
            extracted_text, ocr_engine, stt_engine = self._extract_text(payload, warnings)
            if not extracted_text.strip():
                return PipelineResult(
                    extracted_text='',
                    status=PipelineStatus.FAILED,
                    warnings=['텍스트 추출 결과가 비어 있습니다.'],
                )

            task = TaskType.QA if payload.question else TaskType.SUMMARIZE
            llm_result = self._run_llm(extracted_text, task, payload.question)

            tts_input = self._build_tts_input(llm_result, task)
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
        except Exception as exc:
            logger.exception('Pipeline execution failed')
            return PipelineResult(
                extracted_text='',
                status=PipelineStatus.FAILED,
                warnings=[f'파이프라인 오류: {exc}'],
            )

    def _extract_text(
        self,
        payload: InputPayload,
        warnings: list[str],
    ) -> tuple[str, str | None, str | None]:
        """
        입력 타입에 따라 OCR, PDF, STT 또는 사전 추출 텍스트 경로로 분기한다.

        Returns:
            tuple[str, str | None, str | None]:
                추출 텍스트, OCR 엔진명, STT 엔진명
        """
        match payload.input_type:
            case InputType.IMAGE:
                return self._run_image(payload.content, warnings)
            case InputType.PDF:
                return self._run_pdf(payload.content, warnings)
            case InputType.AUDIO:
                return self._run_audio(payload.content)
            case InputType.QUESTION:
                return self._decode_question_context(payload.content), None, None
            case _:
                raise ValueError(f'지원하지 않는 입력 타입: {payload.input_type}')

    def _run_image(
        self,
        content: bytes,
        warnings: list[str],
    ) -> tuple[str, str | None, str | None]:
        """이미지 바이트를 OCR 처리한다."""
        result = self.ocr.recognize(content)
        if result.avg_confidence < 0.75:
            warnings.append(
                f'OCR 품질 낮음 (avg_conf={result.avg_confidence:.2f}). '
                f'엔진: {result.engine}'
            )
        logger.info(
            '[ocr] engine=%s avg_conf=%.2f',
            result.engine,
            result.avg_confidence,
        )
        return result.raw_text, result.engine, None

    def _run_pdf(
        self,
        content: bytes,
        warnings: list[str],
    ) -> tuple[str, str | None, str | None]:
        """PDF를 텍스트 추출 또는 OCR 경로로 처리한다."""
        result: PDFResult = self.pdf.extract(content)
        engine = 'ocr(scanned)' if result.is_scanned else 'pypdf'
        if result.is_scanned:
            warnings.append('스캔형 PDF로 판별되어 OCR로 처리했습니다.')
        logger.info('[pdf] engine=%s pages=%d', engine, result.page_count)
        return result.text, engine, None

    def _run_audio(self, content: bytes) -> tuple[str, str | None, str | None]:
        """오디오 바이트를 STT 처리한다."""
        result: STTResult = self.stt.transcribe(content)
        logger.info('[stt] engine=%s lang=%s', result.engine, result.language)
        return result.text, None, result.engine

    def _decode_question_context(self, content: bytes) -> str:
        """
        이미 추출된 텍스트를 UTF-8 바이트에서 복원한다.

        QUESTION 타입은 업로드 파일이 아니라 이미 확보된 텍스트 본문에 대한
        질의응답을 위해 사용한다.
        """
        try:
            return content.decode('utf-8').strip()
        except UnicodeDecodeError as exc:
            raise ValueError('QUESTION 타입 content는 UTF-8 텍스트 바이트여야 합니다.') from exc

    def _run_llm(
        self,
        text: str,
        task: TaskType,
        question: str | None,
    ) -> LLMResult:
        """LLM 분석을 실행한다."""
        result = self.llm.generate(text, task, question)
        logger.info('[llm] engine=%s task=%s', result.engine, task.value)
        return result

    def _build_tts_input(self, llm_result: LLMResult, task: TaskType) -> str:
        """TTS에 넘길 본문을 결정한다."""
        if task is TaskType.QA and llm_result.qa_answer:
            return llm_result.qa_answer
        return llm_result.summary

    def _run_tts(
        self,
        text: str,
        voice_preset: str,
        warnings: list[str],
    ) -> TTSResult | None:
        """TTS를 실행하고 실패 시 경고만 남긴다."""
        try:
            result = self.tts.synthesize(text, voice_preset)
            logger.info(
                '[tts] engine=%s voice=%s duration=%.2fs',
                result.engine,
                result.voice_preset,
                result.duration_sec,
            )
            return result
        except Exception as exc:
            warnings.append(f'TTS 실패 (오디오 생략): {exc}')
            logger.warning('[tts] failed: %s', exc)
            return None


def create_default_reading_pipeline() -> ReadingPipeline:
    """
    현재 코드베이스 기준 기본 엔진 조합으로 파이프라인을 구성한다.

    Returns:
        ReadingPipeline: 기본 서비스 조합이 연결된 오케스트레이터
    """
    from services.ocr_service import Qwen2VLEngine
    from services.pdf_service import PyPDFEngine
    from services.llm_remote import RemoteLLM
    from services.stt_whisper_service import ReadMateSTT
    from services.tts_zonos import ZonosTTSEngine
    from services.tts_unavailable import UnavailableTTSEngine

    ocr = Qwen2VLEngine()
    try:
        tts_engine: BaseTTS = ZonosTTSEngine()
    except Exception as exc:
        reason = (
            'Zonos TTS 초기화 실패: '
            f'{exc}. `uv sync`로 의존성을 맞추고, macOS/Linux는 '
            '`brew install espeak-ng`도 확인하세요.'
        )
        logger.warning('[tts] fallback to unavailable engine: %s', reason)
        tts_engine = UnavailableTTSEngine(reason)

    return ReadingPipeline(
        ocr=ocr,
        pdf=PyPDFEngine(ocr_fallback=ocr),
        stt=ReadMateSTT(),
        llm=RemoteLLM(),
        tts=tts_engine,
    )
