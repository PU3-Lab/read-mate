"""
ReadMate용 OpenAI API 기반 LLM 서비스 구현체.
QwenLLM 폴백 또는 독립 엔진으로 사용한다.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import OpenAI

from core.config import (
    LLM_MAX_INPUT_CHARS,
    LLM_MAX_NEW_TOKENS,
    LLM_MAX_RETRIES,
    LLM_MODEL_API,
    OPENAI_API_KEY,
)
from models.schemas import LLMResult, QuizItem, TaskType
from services.llm_base import ChunkedLLM

logger = logging.getLogger(__name__)


class OpenAILLM(ChunkedLLM):
    """OpenAI API 기반 ReadMate LLM 서비스."""

    def __init__(
        self,
        model_name: str = LLM_MODEL_API,
        max_input_chars: int = LLM_MAX_INPUT_CHARS,
        max_new_tokens: int = LLM_MAX_NEW_TOKENS,
        api_key: str | None = None,
    ) -> None:
        """
        OpenAI LLM 서비스를 초기화한다.

        Args:
            model_name: OpenAI 모델 이름 (gpt-4.1-mini 등)
            max_input_chars: 프롬프트에 포함할 최대 본문 길이
            max_new_tokens: 생성 최대 토큰 수
            api_key: OpenAI API 키 (미입력 시 config의 OPENAI_API_KEY 사용)
        """
        self.model_name = model_name
        self.max_input_chars = max_input_chars
        self.max_new_tokens = max_new_tokens
        self.client = OpenAI(api_key=api_key or OPENAI_API_KEY or None)

    def _generate_single(
        self, text: str, task: TaskType, question: str | None
    ) -> LLMResult:
        """
        단일 청크 텍스트에 대해 OpenAI API 추론을 실행한다.

        Args:
            text: 정리된 본문 (max_input_chars 이하)
            task: 요청 태스크
            question: 사용자 질문

        Returns:
            LLMResult: 정규화된 LLM 결과
        """
        normalized_text = text[: self.max_input_chars]
        last_error: Exception | None = None
        for attempt in range(1, LLM_MAX_RETRIES + 1):
            try:
                prompt = self._build_prompt(
                    text=normalized_text,
                    task=task,
                    question=question,
                    attempt=attempt,
                )
                raw_output = self._run_inference(prompt)
                payload = self._parse_json_output(raw_output)
                result = self._to_result(payload)
                if task is TaskType.QA and not result.qa_answer:
                    raise ValueError('QA 태스크에서 qa_answer가 비어 있습니다.')
                return result
            except Exception as exc:
                last_error = exc
                logger.warning(
                    '[openai-llm] parse/inference retry=%s/%s failed: %s',
                    attempt,
                    LLM_MAX_RETRIES,
                    exc,
                )

        logger.error('[openai-llm] all retries failed: %s', last_error)
        return self._build_fallback_result(task, question)

    def _build_prompt(
        self,
        text: str,
        task: TaskType,
        question: str | None,
        attempt: int,
    ) -> str:
        """
        태스크별 JSON 강제 프롬프트를 구성한다.

        Args:
            text: 정리된 본문
            task: 요청 태스크
            question: 사용자 질문
            attempt: 재시도 횟수

        Returns:
            str: 모델 입력 프롬프트
        """
        json_contract = (
            '{'
            '"summary": "문자열", '
            '"key_points": ["문자열"], '
            '"qa_answer": "문자열 또는 null", '
            '"quiz": ['
            '{"question": "문자열", "options": ["문자열"], "answer_index": 0}'
            '] 또는 null'
            '}'
        )

        task_instruction = (
            '본문을 3~5문장으로 요약하고 핵심 포인트를 3개 이상 정리하세요.'
            if task is TaskType.SUMMARIZE
            else (
                '질문에 대해 본문 근거만 사용해 답하세요. '
                '답을 찾기 어려우면 모른다고 분명히 쓰세요. '
                '반드시 qa_answer 필드에 답변을 작성하세요.'
            )
        )

        retry_instruction = (
            '\n이전 응답은 JSON 파싱에 실패했습니다. '
            '설명문 없이 JSON 객체 하나만 반환하세요.'
            if attempt > 1
            else ''
        )

        question_block = f'\n질문: {question}' if question else ''

        return (
            '당신은 학습 보조 도구 ReadMate의 분석 엔진입니다.\n'
            '항상 한국어로 답하고, JSON 객체 하나만 반환하세요.\n'
            f'반환 형식: {json_contract}\n'
            '규칙:\n'
            '- summary는 자연스러운 한국어 문단으로 작성합니다.\n'
            '- key_points는 중복 없이 작성합니다.\n'
            '- QA이면 qa_answer에 반드시 답변을 작성합니다.\n'
            '- QA가 아니면 qa_answer는 null로 둡니다.\n'
            '- quiz는 현재 지원하지 않으면 null로 둡니다.\n'
            f'- 작업 지시: {task_instruction}{retry_instruction}\n\n'
            f'본문:\n{text}\n'
            f'{question_block}\n'
        )

    def _run_inference(self, prompt: str) -> str:
        """
        OpenAI Chat Completions API를 호출해 생성 텍스트를 반환한다.

        Args:
            prompt: 모델 입력 프롬프트

        Returns:
            str: 생성된 원문 텍스트
        """
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    'role': 'system',
                    'content': '당신은 JSON만 반환하는 정확한 도우미입니다.',
                },
                {'role': 'user', 'content': prompt},
            ],
            max_tokens=self.max_new_tokens,
            temperature=0,
            response_format={'type': 'json_object'},
        )
        return (response.choices[0].message.content or '').strip()

    def _parse_json_output(self, raw_output: str) -> dict[str, Any]:
        """
        모델 출력에서 JSON 객체를 추출해 파싱한다.

        Args:
            raw_output: 모델이 생성한 텍스트

        Returns:
            dict[str, Any]: 파싱된 JSON 딕셔너리
        """
        try:
            payload = json.loads(raw_output)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', raw_output, re.DOTALL)
            if not match:
                raise ValueError('JSON 객체를 찾지 못했습니다.') from None
            payload = json.loads(match.group(0))

        if not isinstance(payload, dict):
            raise TypeError('LLM JSON 응답은 객체여야 합니다.')
        return payload

    def _to_result(self, payload: dict[str, Any]) -> LLMResult:
        """
        파싱된 JSON을 LLMResult로 정규화한다.

        Args:
            payload: 모델 JSON 응답

        Returns:
            LLMResult: 파이프라인용 결과 객체
        """
        summary = str(payload.get('summary') or '').strip()
        raw_key_points = payload.get('key_points') or []
        key_points = [str(item).strip() for item in raw_key_points if str(item).strip()]
        qa_answer = payload.get('qa_answer')
        quiz = self._parse_quiz(payload.get('quiz'))

        if not summary:
            raise ValueError('summary가 비어 있습니다.')
        if not key_points:
            raise ValueError('key_points가 비어 있습니다.')

        return LLMResult(
            summary=summary,
            key_points=key_points,
            qa_answer=str(qa_answer).strip() if qa_answer else None,
            quiz=quiz,
            engine=self.model_name,
        )

    def _parse_quiz(self, raw_quiz: Any) -> list[QuizItem] | None:
        """
        퀴즈 목록을 안전하게 파싱한다.

        Args:
            raw_quiz: JSON 응답의 quiz 필드

        Returns:
            list[QuizItem] | None: 정규화된 퀴즈 목록
        """
        if not isinstance(raw_quiz, list):
            return None

        quiz_items: list[QuizItem] = []
        for item in raw_quiz:
            if not isinstance(item, dict):
                continue
            question = str(item.get('question') or '').strip()
            options = item.get('options') or []
            answer_index = item.get('answer_index')
            if (
                not question
                or not isinstance(options, list)
                or not options
                or not isinstance(answer_index, int)
            ):
                continue
            quiz_items.append(
                QuizItem(
                    question=question,
                    options=[str(option).strip() for option in options],
                    answer_index=answer_index,
                )
            )

        return quiz_items or None

    def _build_fallback_result(
        self,
        task: TaskType,
        question: str | None,
    ) -> LLMResult:
        """
        모델 실패 시 최소 결과 포맷을 반환한다.

        Args:
            task: 요청 태스크
            question: 사용자 질문

        Returns:
            LLMResult: 안전한 기본 응답
        """
        qa_answer = None
        if task is TaskType.QA:
            qa_answer = (
                f'질문 "{question}"에 대한 답변을 안정적으로 생성하지 못했습니다.'
                if question
                else '질문에 대한 답변을 안정적으로 생성하지 못했습니다.'
            )

        return LLMResult(
            summary='요약을 안정적으로 생성하지 못했습니다.',
            key_points=['모델 응답 파싱에 실패했습니다.'],
            qa_answer=qa_answer,
            quiz=None,
            engine=self.model_name,
        )
