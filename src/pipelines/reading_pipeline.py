"""
ReadMate 메인 파이프라인 오케스트레이터.
입력 타입에 따라 OCR/PDF/STT 경로를 분기하고 LLM, TTS를 순서대로 실행한다.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

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

SUPPORTED_INPUT_TYPES: dict[str, InputType] = {
    '.png': InputType.IMAGE,
    '.jpg': InputType.IMAGE,
    '.jpeg': InputType.IMAGE,
    '.webp': InputType.IMAGE,
    '.bmp': InputType.IMAGE,
    '.pdf': InputType.PDF,
    '.mp3': InputType.AUDIO,
    '.wav': InputType.AUDIO,
    '.m4a': InputType.AUDIO,
    '.ogg': InputType.AUDIO,
    '.flac': InputType.AUDIO,
}


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

    def run(self, payload: InputPayload, on_progress: Any | None = None) -> PipelineResult:
        """
        입력 타입에 따라 적절한 경로로 분기해 전체 파이프라인을 실행한다.

        Args:
            payload: 입력 파일 정보, 질문, 음성 프리셋을 포함한 요청 데이터
            on_progress: 진행 상황을 보고할 콜백 함수 (str 인자)

        Returns:
            PipelineResult: 추출 텍스트, LLM 결과, TTS 결과, 경고 목록
        """
        result = self.run_analysis(payload, on_progress=on_progress)
        if result.status is not PipelineStatus.SUCCESS or result.llm_result is None:
            return result

        if on_progress:
            on_progress('음성 합성 준비 중...')

        task = TaskType.QA if payload.question else TaskType.SUMMARIZE
        result.tts_result = self.synthesize_text(
            self._build_tts_input(result.llm_result, task),
            payload.voice_preset,
            result.warnings,
        )
        return result

    def run_analysis(self, payload: InputPayload, on_progress: Any | None = None) -> PipelineResult:
        """
        입력에서 텍스트 추출과 LLM 분석까지만 실행한다.

        Args:
            payload: 입력 파일 정보, 질문, 음성 프리셋을 포함한 요청 데이터
            on_progress: 진행 상황을 보고할 콜백 함수 (str 인자)

        Returns:
            PipelineResult: 추출 텍스트와 LLM 결과가 채워진 분석 결과
        """
        warnings: list[str] = []

        try:
            if on_progress:
                msg = (
                    'OCR 처리 중...'
                    if payload.input_type in (InputType.IMAGE, InputType.PDF)
                    else '음성 인식 중...'
                    if payload.input_type == InputType.AUDIO
                    else '텍스트 추출 중...'
                )
                on_progress(msg)

            if payload.input_type in (InputType.IMAGE, InputType.PDF):
                logger.info('ocr 추출중')
            extracted_text, ocr_engine, stt_engine = self._extract_text(payload, warnings)
            if payload.input_type in (InputType.IMAGE, InputType.PDF):
                logger.info('ocr 추출완료')
            if not extracted_text.strip():
                return PipelineResult(
                    extracted_text='',
                    status=PipelineStatus.FAILED,
                    warnings=['텍스트 추출 결과가 비어 있습니다.'],
                )

            if on_progress:
                on_progress('LLM 분석 및 요약 중...')

            task = TaskType.QA if payload.question else TaskType.SUMMARIZE
            llm_result = self._run_llm(extracted_text, task, payload.question)

            return PipelineResult(
                extracted_text=extracted_text,
                llm_result=llm_result,
                tts_result=None,
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

    def synthesize_text(
        self,
        text: str,
        voice_preset: str = 'default',
        warnings: list[str] | None = None,
    ) -> TTSResult | None:
        """
        주어진 텍스트로 TTS를 실행한다.

        Args:
            text: 음성으로 합성할 텍스트
            voice_preset: 사용할 프리셋 목소리
            warnings: 실패 시 경고를 누적할 목록

        Returns:
            TTSResult | None: 성공 시 TTS 결과, 실패 시 None
        """
        warning_list = warnings if warnings is not None else []
        return self._run_tts(text, voice_preset, warning_list)

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
    from services.llm_remote import RemoteLLM
    from services.ocr_service import Qwen2VLEngine
    from services.pdf_service import PyPDFEngine
    from services.stt_whisper_service import ReadMateSTT
    from services.tts_unavailable import UnavailableTTSEngine
    from services.tts_zonos import ZonosTTSEngine

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


@lru_cache(maxsize=1)
def get_default_reading_pipeline() -> ReadingPipeline:
    """기본 ReadingPipeline 인스턴스를 캐시해 재사용한다."""
    return create_default_reading_pipeline()


def infer_input_type(file_name: str) -> InputType:
    """
    파일 확장자로 파이프라인 입력 타입을 판별한다.

    Args:
        file_name: 업로드 파일 이름

    Returns:
        InputType: 파이프라인 입력 타입

    Raises:
        ValueError: 지원하지 않는 확장자일 때
    """
    suffix = Path(file_name).suffix.lower()
    input_type = SUPPORTED_INPUT_TYPES.get(suffix)
    if input_type is None:
        raise ValueError(f'지원하지 않는 파일 형식입니다: {suffix or "(확장자 없음)"}')
    return input_type


def build_input_payload(
    file_name: str,
    content: bytes,
    question: str | None = None,
    voice_preset: str = 'default',
) -> InputPayload:
    """
    UI 입력을 파이프라인 입력으로 변환한다.

    Args:
        file_name: 업로드 파일 이름
        content: 파일 원본 바이트
        question: 질문 텍스트
        voice_preset: TTS 프리셋 이름

    Returns:
        InputPayload: 파이프라인 요청 객체
    """
    return InputPayload(
        input_type=infer_input_type(file_name),
        file_name=file_name,
        content=content,
        question=(question or '').strip() or None,
        voice_preset=voice_preset.strip() or 'default',
    )


def analyze_content(
    file_name: str,
    content: bytes,
    voice_preset: str = 'default',
    on_progress: Any | None = None,
) -> dict[str, object]:
    """
    파일을 기본 ReadingPipeline으로 분석하고 frontend 상태 형식으로 변환한다.

    Args:
        file_name: 업로드 파일 이름
        content: 파일 원본 바이트
        voice_preset: TTS 프리셋 이름
        on_progress: 진행 상황을 보고할 콜백 함수

    Returns:
        dict[str, object]: frontend 세션 상태에 바로 넣을 수 있는 값
    """
    payload = build_input_payload(
        file_name=file_name,
        content=content,
        voice_preset=voice_preset,
    )
    result = get_default_reading_pipeline().run_analysis(payload, on_progress=on_progress)
    return to_frontend_state(result)


def synthesize_summary_audio(
    summary: str,
    voice_preset: str = 'default',
) -> dict[str, object]:
    """
    요약 텍스트를 음성으로 합성해 frontend 상태 형식으로 돌려준다.

    Args:
        summary: 요약 본문 텍스트
        voice_preset: TTS 프리셋 이름

    Returns:
        dict[str, object]: audio bytes와 경고 목록
    """
    warnings: list[str] = []
    normalized_summary = summary.strip()
    if not normalized_summary:
        return {
            'audio_bytes': None,
            'pipeline_warnings': ['TTS 생성할 요약이 비어 있습니다.'],
        }

    tts_result = get_default_reading_pipeline().synthesize_text(
        normalized_summary,
        voice_preset=voice_preset,
        warnings=warnings,
    )
    if tts_result is None:
        return {
            'audio_bytes': None,
            'pipeline_warnings': warnings,
        }

    audio_path = Path(tts_result.audio_path)
    audio_bytes = audio_path.read_bytes() if audio_path.exists() else None
    return {
        'audio_bytes': audio_bytes,
        'pipeline_warnings': warnings,
    }


def answer_question(question: str, context: str) -> str:
    """
    기존 본문을 기반으로 질문 답변을 생성한다.

    Args:
        question: 사용자 질문
        context: 이미 추출된 본문

    Returns:
        str: 질의응답 결과 텍스트
    """
    normalized_question = question.strip()
    normalized_context = context.strip()
    if not normalized_question:
        raise ValueError('질문이 비어 있습니다.')
    if not normalized_context:
        raise ValueError('질문할 본문이 없습니다.')

    llm_result = get_default_reading_pipeline().llm.generate(
        normalized_context,
        TaskType.QA,
        normalized_question,
    )
    return (llm_result.qa_answer or llm_result.summary).strip()


def to_frontend_state(result: PipelineResult) -> dict[str, object]:
    """
    파이프라인 결과를 frontend 세션 상태 구조로 변환한다.

    Args:
        result: 파이프라인 실행 결과

    Returns:
        dict[str, object]: frontend 상태 딕셔너리

    Raises:
        RuntimeError: 파이프라인 실패 또는 LLM 결과 누락 시
    """
    if result.status is not PipelineStatus.SUCCESS:
        warning_text = '\n'.join(result.warnings) or '알 수 없는 오류'
        raise RuntimeError(f'파이프라인 실행 실패: {warning_text}')

    if result.llm_result is None:
        raise RuntimeError('LLM 결과가 비어 있습니다.')

    return {
        'raw_text': result.extracted_text,
        'summary': result.llm_result.summary,
        'quiz': _normalize_quiz(result.llm_result.quiz),
        'memo_keywords': result.llm_result.key_points,
        'audio_bytes': _read_audio_bytes(result),
        'pipeline_warnings': result.warnings,
    }


def _normalize_quiz(quiz: list | None) -> list[dict[str, object]]:
    """
    QuizItem 목록을 frontend 퀴즈 패널 형식으로 바꾼다.

    Args:
        quiz: 파이프라인 퀴즈 결과

    Returns:
        list[dict[str, object]]: frontend 퀴즈 데이터
    """
    if not quiz:
        return []

    return [
        {
            'q': item.question,
            'options': item.options,
            'answer': item.answer_index,
        }
        for item in quiz
    ]


def _read_audio_bytes(result: PipelineResult) -> bytes | None:
    """
    TTS 결과 파일을 읽어 audio bytes로 변환한다.

    Args:
        result: 파이프라인 실행 결과

    Returns:
        bytes | None: 재생 가능한 오디오 바이트
    """
    if result.tts_result is None:
        return None

    audio_path = Path(result.tts_result.audio_path)
    if not audio_path.exists():
        return None

    return audio_path.read_bytes()
