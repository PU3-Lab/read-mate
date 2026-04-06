"""frontend ReadingPipeline 어댑터 테스트."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from models.schemas import (
    LLMResult,
    PipelineResult,
    PipelineStatus,
    QuizItem,
    TaskType,
    TTSResult,
)

MODULE_PATH = Path(__file__).resolve().parents[1] / 'src' / 'pipelines' / 'reading_pipeline.py'
SPEC = importlib.util.spec_from_file_location('reading_pipeline_module', MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
pipeline_service = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline_service)


class FakeLLM:
    """질문 응답 검사용 LLM 더블."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, object, str | None]] = []

    def generate(
        self,
        text: str,
        task: object,
        question: str | None = None,
    ) -> LLMResult:
        self.calls.append((text, task, question))
        return LLMResult(
            summary='요약 응답',
            key_points=['핵심 1'],
            qa_answer='질문 답변',
            engine='fake-llm',
        )


class FakePipeline:
    """frontend 어댑터 테스트용 파이프라인 더블."""

    def __init__(self, result: PipelineResult) -> None:
        self.result = result
        self.llm = FakeLLM()

    def run(self, payload: object) -> PipelineResult:
        return self.result


def test_infer_input_type_for_material_file() -> None:
    """frontend 어댑터는 PDF를 PDF 타입으로 판별한다."""
    assert pipeline_service.infer_input_type('lecture.pdf').value == 'pdf'


def test_to_frontend_state_maps_pipeline_result(tmp_path: Path) -> None:
    """파이프라인 결과를 frontend 세션 상태 구조로 바꾼다."""
    audio_path = tmp_path / 'summary.wav'
    audio_path.write_bytes(b'wav-bytes')

    result = PipelineResult(
        extracted_text='원문 텍스트',
        llm_result=LLMResult(
            summary='요약 결과',
            key_points=['포인트 1', '포인트 2'],
            quiz=[
                QuizItem(
                    question='문제 1',
                    options=['A', 'B', 'C', 'D'],
                    answer_index=1,
                )
            ],
            engine='fake-llm',
        ),
        tts_result=TTSResult(
            audio_path=str(audio_path),
            voice_preset='default',
            engine='fake-tts',
            duration_sec=1.2,
        ),
        status=PipelineStatus.SUCCESS,
        warnings=['경고 1'],
    )

    state = pipeline_service.to_frontend_state(result)

    assert state['raw_text'] == '원문 텍스트'
    assert state['summary'] == '요약 결과'
    assert state['memo_keywords'] == ['포인트 1', '포인트 2']
    assert state['audio_bytes'] == b'wav-bytes'
    assert state['pipeline_warnings'] == ['경고 1']
    assert state['quiz'] == [
        {
            'q': '문제 1',
            'options': ['A', 'B', 'C', 'D'],
            'answer': 1,
        }
    ]


def test_answer_question_uses_pipeline_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """질문 답변은 파이프라인의 LLM 어댑터를 사용한다."""
    fake_pipeline = FakePipeline(
        PipelineResult(
            extracted_text='',
            status=PipelineStatus.SUCCESS,
        )
    )
    monkeypatch.setattr(
        pipeline_service,
        'get_default_reading_pipeline',
        lambda: fake_pipeline,
    )

    answer = pipeline_service.answer_question('질문', '본문')

    assert answer == '질문 답변'
    assert fake_pipeline.llm.calls
    assert fake_pipeline.llm.calls[0][0] == '본문'
    assert fake_pipeline.llm.calls[0][1] is TaskType.QA
    assert fake_pipeline.llm.calls[0][2] == '질문'


def test_to_frontend_state_raises_on_failed_pipeline() -> None:
    """파이프라인 실패는 예외로 올린다."""
    result = PipelineResult(
        extracted_text='',
        status=PipelineStatus.FAILED,
        warnings=['실패 이유'],
    )

    with pytest.raises(RuntimeError, match='실패 이유'):
        pipeline_service.to_frontend_state(result)
