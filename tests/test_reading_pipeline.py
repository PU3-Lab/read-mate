"""ReadingPipeline 오케스트레이션 테스트."""

from __future__ import annotations

from dataclasses import dataclass

from models.schemas import (
    InputPayload,
    InputType,
    LLMResult,
    OCRResult,
    PDFResult,
    PipelineStatus,
    STTResult,
    STTSegment,
    TaskType,
    TTSResult,
)
from pipelines.reading_pipeline import ReadingPipeline
from services.base import BaseLLM, BaseOCR, BasePDF, BaseSTT, BaseTTS
from services.tts_unavailable import UnavailableTTSEngine


@dataclass
class CallLog:
    """테스트용 호출 기록."""

    tts_text: str | None = None
    llm_task: TaskType | None = None
    llm_question: str | None = None


class StubOCR(BaseOCR):
    """고정 OCR 결과를 반환하는 테스트용 엔진."""

    def recognize(self, image_bytes: bytes) -> OCRResult:
        return OCRResult(
            boxes=[],
            engine='stub-ocr',
            avg_confidence=0.91,
            raw_text='이미지 본문',
        )


class StubPDF(BasePDF):
    """고정 PDF 결과를 반환하는 테스트용 엔진."""

    def extract(self, pdf_bytes: bytes) -> PDFResult:
        return PDFResult(
            text='PDF 본문',
            page_count=2,
            is_scanned=False,
        )


class StubSTT(BaseSTT):
    """고정 STT 결과를 반환하는 테스트용 엔진."""

    def transcribe(self, audio_bytes: bytes) -> STTResult:
        return STTResult(
            text='오디오 본문',
            language='ko',
            segments=[STTSegment(start=0.0, end=1.0, text='오디오 본문')],
            engine='stub-stt',
        )


class StubLLM(BaseLLM):
    """호출 인자를 기록하는 테스트용 LLM."""

    def __init__(self, log: CallLog) -> None:
        self._log = log

    def generate(
        self,
        text: str,
        task: TaskType,
        question: str | None = None,
    ) -> LLMResult:
        self._log.llm_task = task
        self._log.llm_question = question

        if task is TaskType.QA:
            return LLMResult(
                summary='질문 응답용 요약',
                key_points=['포인트 1'],
                qa_answer=f'답변: {question}',
                engine='stub-llm',
            )

        return LLMResult(
            summary=f'요약: {text}',
            key_points=['포인트 1'],
            engine='stub-llm',
        )


class StubTTS(BaseTTS):
    """호출 인자를 기록하는 테스트용 TTS."""

    def __init__(self, log: CallLog) -> None:
        self._log = log

    def synthesize(self, text: str, voice_preset: str = 'default') -> TTSResult:
        self._log.tts_text = text
        return TTSResult(
            audio_path='/tmp/fake.wav',
            voice_preset=voice_preset,
            engine='stub-tts',
            duration_sec=0.1,
        )

    def list_presets(self) -> list[str]:
        return ['default']


class FailingTTS(StubTTS):
    """실패를 발생시키는 테스트용 TTS."""

    def synthesize(self, text: str, voice_preset: str = 'default') -> TTSResult:
        raise RuntimeError('tts failed')


def _build_pipeline(log: CallLog, tts: BaseTTS | None = None) -> ReadingPipeline:
    """공통 테스트 파이프라인 생성."""
    return ReadingPipeline(
        ocr=StubOCR(),
        pdf=StubPDF(),
        stt=StubSTT(),
        llm=StubLLM(log),
        tts=tts or StubTTS(log),
    )


def test_reading_pipeline_runs_image_to_summary() -> None:
    """이미지 입력 시 OCR -> 요약 -> TTS 순서로 처리한다."""
    log = CallLog()
    pipeline = _build_pipeline(log)

    result = pipeline.run(
        InputPayload(
            input_type=InputType.IMAGE,
            file_name='sample.png',
            content=b'image-bytes',
        )
    )

    assert result.status is PipelineStatus.SUCCESS
    assert result.extracted_text == '이미지 본문'
    assert result.ocr_engine == 'stub-ocr'
    assert result.llm_result is not None
    assert result.llm_result.summary == '요약: 이미지 본문'
    assert result.tts_result is not None
    assert log.llm_task is TaskType.SUMMARIZE
    assert log.tts_text == '요약: 이미지 본문'


def test_reading_pipeline_uses_qa_answer_for_tts() -> None:
    """질문이 있으면 QA 태스크로 실행하고 답변을 TTS 입력으로 사용한다."""
    log = CallLog()
    pipeline = _build_pipeline(log)

    result = pipeline.run(
        InputPayload(
            input_type=InputType.QUESTION,
            file_name='context.txt',
            content='문맥 본문'.encode('utf-8'),
            question='핵심이 뭐야?',
        )
    )

    assert result.status is PipelineStatus.SUCCESS
    assert result.extracted_text == '문맥 본문'
    assert result.llm_result is not None
    assert result.llm_result.qa_answer == '답변: 핵심이 뭐야?'
    assert log.llm_task is TaskType.QA
    assert log.llm_question == '핵심이 뭐야?'
    assert log.tts_text == '답변: 핵심이 뭐야?'


def test_reading_pipeline_keeps_success_when_tts_fails() -> None:
    """TTS 실패는 경고로만 남기고 파이프라인 전체는 성공 처리한다."""
    log = CallLog()
    pipeline = _build_pipeline(log, tts=FailingTTS(log))

    result = pipeline.run(
        InputPayload(
            input_type=InputType.PDF,
            file_name='sample.pdf',
            content=b'pdf-bytes',
        )
    )

    assert result.status is PipelineStatus.SUCCESS
    assert result.tts_result is None
    assert any('TTS 실패' in warning for warning in result.warnings)


def test_reading_pipeline_keeps_success_with_unavailable_tts() -> None:
    """초기화 실패로 비활성화된 TTS도 경고만 남기고 계속 진행한다."""
    log = CallLog()
    pipeline = _build_pipeline(
        log,
        tts=UnavailableTTSEngine('phonemizer가 설치되어 있지 않습니다.'),
    )

    result = pipeline.run(
        InputPayload(
            input_type=InputType.IMAGE,
            file_name='sample.png',
            content=b'image-bytes',
        )
    )

    assert result.status is PipelineStatus.SUCCESS
    assert result.tts_result is None
    assert any('phonemizer가 설치되어 있지 않습니다.' in warning for warning in result.warnings)
