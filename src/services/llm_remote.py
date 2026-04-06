"""
ReadMate LLM 서버를 BaseLLM 인터페이스로 감싸는 원격 어댑터.
파이프라인은 로컬 모델 대신 HTTP API를 통해 요약과 QA를 호출한다.
"""

from __future__ import annotations

import logging

from api.client import LLMClient
from core.config import LLM_SERVER_URL
from models.schemas import LLMResult, TaskType
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
            else:
                response = self.client.summarize(text)
        except Exception as exc:
            logger.exception('[remote-llm] request failed')
            raise RuntimeError(f'LLM 서버 호출 실패: {exc}') from exc

        return LLMResult(
            summary=response.summary,
            key_points=response.key_points,
            qa_answer=response.qa_answer,
            engine=response.engine,
        )
