"""RemoteLLM 테스트."""

from __future__ import annotations

import pytest

from api.schemas import LLMResponse
from models.schemas import TaskType
from services.llm_remote import RemoteLLM


class StubLLMClient:
    """RemoteLLM 테스트용 스텁 클라이언트."""

    def summarize(self, text: str) -> LLMResponse:
        return LLMResponse(
            summary=f'요약: {text}',
            key_points=['핵심 1', '핵심 2'],
            engine='stub-server',
        )

    def qa(self, text: str, question: str) -> LLMResponse:
        return LLMResponse(
            summary='질문용 요약',
            key_points=['핵심 1'],
            qa_answer=f'답변: {question}',
            engine='stub-server',
        )


class FailingLLMClient:
    """실패를 발생시키는 스텁 클라이언트."""

    def summarize(self, text: str) -> LLMResponse:
        raise ConnectionError('server down')


def test_remote_llm_summarize_returns_llm_result() -> None:
    """summarize 응답을 LLMResult로 변환한다."""
    llm = RemoteLLM(client=StubLLMClient())

    result = llm.generate('본문', TaskType.SUMMARIZE)

    assert result.summary == '요약: 본문'
    assert result.key_points == ['핵심 1', '핵심 2']
    assert result.qa_answer is None
    assert result.engine == 'stub-server'


def test_remote_llm_qa_returns_llm_result() -> None:
    """qa 응답을 LLMResult로 변환한다."""
    llm = RemoteLLM(client=StubLLMClient())

    result = llm.generate('본문', TaskType.QA, '무슨 내용이야?')

    assert result.summary == '질문용 요약'
    assert result.qa_answer == '답변: 무슨 내용이야?'
    assert result.engine == 'stub-server'


def test_remote_llm_requires_question_for_qa() -> None:
    """QA 태스크에는 질문이 필요하다."""
    llm = RemoteLLM(client=StubLLMClient())

    with pytest.raises(ValueError):
        llm.generate('본문', TaskType.QA)


def test_remote_llm_wraps_request_error() -> None:
    """서버 호출 실패를 RuntimeError로 감싼다."""
    llm = RemoteLLM(client=FailingLLMClient())

    with pytest.raises(RuntimeError, match='LLM 서버 호출 실패'):
        llm.generate('본문', TaskType.SUMMARIZE)
