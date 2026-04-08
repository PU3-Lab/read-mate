"""
ReadMate LLM 서버를 BaseLLM 인터페이스로 감싸는 원격 어댑터.
파이프라인은 로컬 모델 대신 HTTP API를 통해 요약과 QA를 호출한다.
"""

from __future__ import annotations

import logging

from api.client import LLMClient
from core.config import LLM_SERVER_URL
from models.schemas import LLMResult, QuizEvalResult, TaskType
from services.base import BaseLLM

logger = logging.getLogger(__name__)


class RemoteLLM(BaseLLM):
    """HTTP 기반 LLM 서버 어댑터."""

    def __init__(
        self,
        base_url: str = LLM_SERVER_URL,
        timeout: float = 120.0,
        client: LLMClient | None = None,
    ) -> None:
        """
        Args:
            base_url: LLM 서버 기본 URL
            timeout: 요청 타임아웃 (초)
            client: 테스트나 커스텀 연결을 위한 주입 클라이언트
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.client = client or LLMClient(base_url=self.base_url, timeout=timeout)

    def generate(
        self,
        text: str,
        task: TaskType,
        question: str | None = None,
    ) -> LLMResult:
        """
        LLM 서버에 요약 또는 QA를 요청한다.

        Args:
            text: 분석할 본문
            task: SUMMARIZE 또는 QA
            question: QA 태스크일 때 사용자 질문

        Returns:
            LLMResult: 서버 응답을 파이프라인 결과 객체로 변환한 값
        """
        if not text.strip():
            raise ValueError('LLM 입력 텍스트가 비어 있습니다.')
        if task is TaskType.QA and not (question or '').strip():
            raise ValueError('QA 태스크에는 question이 필요합니다.')

        try:
            if task is TaskType.QA:
                response = self.client.qa(text, question)
                return LLMResult(
                    summary=response.summary,
                    key_points=response.key_points,
                    qa_answer=response.qa_answer,
                    engine=response.engine,
                )
            elif task is TaskType.QUIZ:
                quiz_response = self.client.quiz(text)
                from models.schemas import QuizItem
                return LLMResult(
                    summary='',
                    key_points=[],
                    quiz=[
                        QuizItem(
                            question=item.question,
                            options=item.options,
                            answer_index=item.answer_index,
                        )
                        for item in quiz_response.quiz
                    ],
                    engine=quiz_response.engine,
                )
            else:
                response = self.client.summarize(text)
                return LLMResult(
                    summary=response.summary,
                    key_points=response.key_points,
                    qa_answer=response.qa_answer,
                    engine=response.engine,
                )
        except Exception as exc:
            logger.exception('[remote-llm] request failed')
            raise RuntimeError(f'LLM 서버 호출 실패: {exc}') from exc

    def evaluate_answer(
        self,
        question: str,
        options: list[str],
        correct_index: int,
        user_answer: str,
    ) -> QuizEvalResult:
        """사용자의 음성 답변을 채점하고 이유를 설명한다."""
        try:
            response = self.client.evaluate_quiz(question, options, correct_index, user_answer)
            return QuizEvalResult(
                correct=response.correct,
                explanation=response.explanation,
                engine=response.engine,
            )
        except Exception as exc:
            logger.exception('[remote-llm] evaluate_answer failed')
            raise RuntimeError(f'LLM 서버 호출 실패: {exc}') from exc
