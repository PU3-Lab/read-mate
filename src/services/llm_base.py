"""
LLM 공통 청크 처리 로직 (Map-Reduce).
엔진별 구현체(QwenLLM, OpenAILLM 등)는 이 클래스를 상속한다.
"""

from __future__ import annotations

import logging
import re
from abc import abstractmethod

from core.config import LLM_MAX_INPUT_CHARS
from models.schemas import LLMResult, TaskType
from services.base import BaseLLM

logger = logging.getLogger(__name__)

CHUNK_OVERLAP = 200  # 청크 간 문맥 연속성을 위한 겹침 글자 수


class ChunkedLLM(BaseLLM):
    """
    청크 분할 및 Map-Reduce 요약 로직을 공통으로 제공하는 중간 클래스.
    엔진별 구현체는 _generate_single()과 _build_fallback_result()만 구현하면 된다.
    """

    max_input_chars: int = LLM_MAX_INPUT_CHARS

    def generate(
        self, text: str, task: TaskType, question: str | None = None
    ) -> LLMResult:
        """
        텍스트와 태스크 타입을 받아 LLM 결과 반환.
        max_input_chars 초과 시 청크 분할 후 Map-Reduce 방식으로 처리.

        Args:
            text: 분석할 원문 텍스트
            task: SUMMARIZE | QA
            question: QA 태스크일 때 사용자 질문

        Returns:
            LLMResult: 요약, 핵심 정리, 질의응답 답변 등
        """
        cleaned = re.sub(r'\n{3,}', '\n\n', text).strip()
        if not cleaned:
            return self._build_fallback_result(task, question)

        chunks = self._chunk_text(cleaned)
        if len(chunks) > 1:
            logger.info('[llm] long text detected: %d chunks', len(chunks))
            return self._generate_chunked(chunks, task, question)

        return self._generate_single(cleaned, task, question)

    @abstractmethod
    def _generate_single(
        self, text: str, task: TaskType, question: str | None
    ) -> LLMResult:
        """
        단일 청크에 대한 추론을 실행한다. 엔진별로 구현.

        Args:
            text: max_input_chars 이하의 정리된 본문
            task: 요청 태스크
            question: 사용자 질문

        Returns:
            LLMResult: 정규화된 결과
        """
        ...

    @abstractmethod
    def _build_fallback_result(
        self, task: TaskType, question: str | None
    ) -> LLMResult:
        """모델 실패 시 안전한 기본 결과 반환. 엔진별로 구현."""
        ...

    def _chunk_text(self, text: str) -> list[str]:
        """
        텍스트를 max_input_chars 단위로 분할한다.
        청크 간 CHUNK_OVERLAP 글자만큼 겹쳐 문맥 단절을 줄인다.

        Args:
            text: 전체 원문

        Returns:
            list[str]: 분할된 청크 목록
        """
        if len(text) <= self.max_input_chars:
            return [text]

        chunks: list[str] = []
        step = max(self.max_input_chars - CHUNK_OVERLAP, 1)
        start = 0
        while start < len(text):
            chunks.append(text[start : start + self.max_input_chars])
            start += step
        return chunks

    def _generate_chunked(
        self, chunks: list[str], task: TaskType, question: str | None
    ) -> LLMResult:
        """
        청크별 요약 후 합쳐서 최종 요약을 생성한다 (Map-Reduce).

        Args:
            chunks: 분할된 텍스트 청크 목록
            task: 요청 태스크
            question: QA 태스크일 때 사용자 질문

        Returns:
            LLMResult: 최종 병합된 결과
        """
        if task is TaskType.QA and question:
            target_chunks = self._select_relevant_chunks(chunks, question)
            logger.info(
                '[llm] QA relevant chunks selected: %d/%d',
                len(target_chunks),
                len(chunks),
            )
            merged_text = '\n\n'.join(target_chunks)
            return self._generate_single(merged_text, task, question)

        chunk_results: list[LLMResult] = []
        for i, chunk in enumerate(chunks):
            logger.info('[llm] processing chunk %d/%d', i + 1, len(chunks))
            chunk_results.append(self._generate_single(chunk, TaskType.SUMMARIZE, None))

        merged_text = '\n\n'.join(r.summary for r in chunk_results)
        final_result = self._generate_single(merged_text, task, question)

        seen: set[str] = set()
        all_key_points: list[str] = []
        for r in chunk_results:
            for kp in r.key_points:
                if kp not in seen:
                    seen.add(kp)
                    all_key_points.append(kp)

        return LLMResult(
            summary=final_result.summary,
            key_points=final_result.key_points or all_key_points,
            qa_answer=final_result.qa_answer,
            quiz=final_result.quiz,
            engine=final_result.engine,
        )

    def _select_relevant_chunks(self, chunks: list[str], question: str) -> list[str]:
        """
        질문과 겹치는 토큰이 많은 원문 청크를 우선 선택한다.
        긴 문서 QA에서 요약본 대신 원문 근거를 보존하기 위한 처리다.
        """
        question_tokens = self._tokenize(question)
        if not question_tokens:
            return chunks[: min(3, len(chunks))]

        scored_chunks = [
            (self._score_chunk_relevance(chunk, question_tokens), index, chunk)
            for index, chunk in enumerate(chunks)
        ]
        scored_chunks.sort(key=lambda item: (-item[0], item[1]))

        top_chunks = [chunk for score, _, chunk in scored_chunks if score > 0][:3]
        if top_chunks:
            return top_chunks

        return chunks[: min(3, len(chunks))]

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """한글/영문/숫자 기준의 간단한 토큰 집합 생성."""
        return {
            token
            for token in re.findall(r'[가-힣A-Za-z0-9]+', text.lower())
            if len(token) > 1
        }

    def _score_chunk_relevance(self, chunk: str, question_tokens: set[str]) -> int:
        """질문 토큰과 청크 토큰의 단순 겹침 점수 계산."""
        chunk_tokens = self._tokenize(chunk)
        return len(question_tokens & chunk_tokens)
