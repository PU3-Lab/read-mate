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
from models.schemas import LLMResult, QuizEvalResult, QuizItem, TaskType
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
                if task is TaskType.QUIZ and not result.quiz:
                    raise ValueError('QUIZ 태스크에서 quiz가 비어 있습니다.')
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

        if task is TaskType.SUMMARIZE:
            task_instruction = '본문을 3~5문장으로 요약하고 핵심 포인트를 3개 이상 정리하세요.'
        elif task is TaskType.QUIZ:
            task_instruction = (
                '본문 내용을 기반으로 객관식 퀴즈 문제를 정확히 10개 생성하세요. '
                '각 문제는 4개의 보기와 정답 인덱스(0~3)를 포함해야 합니다. '
                'summary 필드에는 본문을 1~2문장으로 간략히 요약하고, '
                'key_points 필드에는 핵심 키워드를 3개 이상 작성하세요. '
                'quiz 필드에 반드시 10개의 문제를 작성하세요.'
            )
        else:
            task_instruction = (
                '질문에 대해 본문 근거만 사용해 답하세요. '
                '답을 찾기 어려우면 모른다고 분명히 쓰세요. '
                '반드시 qa_answer 필드에 답변을 작성하세요.'
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
            '- 단어가 붙지 않도록 띄어쓰기를 정확히 적용할 것\n'
            '- 전문용어, 인명, 지명, 제품명은 원문 표기를 최대한 유지할 것\n'
            '- summary는 자연스러운 한국어 문단으로 작성합니다.\n'
            '- key_points는 중복 없이 작성합니다.\n'
            '- QA이면 qa_answer에 반드시 답변을 작성합니다.\n'
            '- QA가 아니면 qa_answer는 null로 둡니다.\n'
            '- QUIZ이면 quiz 필드에 반드시 10개의 문제를 작성합니다.\n'
            '- QUIZ가 아니면 quiz는 null로 둡니다.\n'
            '- JSON 문자열 내부에 따옴표가 필요한 경우 반드시 \" 로 이스케이프할 것\n'
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
        잘린 JSON의 경우 닫는 괄호를 보정하여 시도한다.

        Args:
            raw_output: 모델이 생성한 텍스트

        Returns:
            dict[str, Any]: 파싱된 JSON 딕셔너리
        """
        cleaned = raw_output.strip()
        
        # 1. 표준 파싱 시도
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 2. 마크다운 코드 블록 제거 후 시도
        if '```json' in cleaned:
            cleaned = cleaned.split('```json')[1].split('```')[0].strip()
        elif '```' in cleaned:
            cleaned = cleaned.split('```')[1].split('```')[0].strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 3. 정규표현식으로 { } 내용 추출 시도
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                cleaned = match.group(0)

        # 4. 잘린 JSON 보정 (Truncated JSON recovery)
        # 응답이 길어서 잘린 경우, 괄호 쌍을 맞춰서 시도해본다.
        temp = cleaned
        # quiz 리스트 내부에서 잘린 경우 닫아줌
        if '"quiz": [' in temp and temp.count('[') > temp.count(']'):
            # 마지막 요소가 불완전하면(쉼표 뒤에 아무것도 없거나 객체가 안 닫힘) 제거 시도
            temp = temp.rstrip(', \n\t')
            if temp.endswith('}'):
                temp += ']'
            else:
                # 마지막 불완전 객체 제거
                last_brace = temp.rfind('{')
                if last_brace > temp.find('"quiz": ['):
                    temp = temp[:last_brace].rstrip(', \n\t') + ']'
        
        # 루트 객체 닫기
        if temp.count('{') > temp.count('}'):
            temp = temp.rstrip(', \n\t')
            temp += '}' * (temp.count('{') - temp.count('}'))

        try:
            payload = json.loads(temp)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError as e:
            logger.debug('[openai-llm] JSON recovery failed: %s', e)

        raise ValueError(f'JSON 파싱에 실패했습니다: {raw_output[:100]}...')

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

    def evaluate_answer(
        self,
        question: str,
        options: list[str],
        correct_index: int,
        user_answer: str,
    ) -> QuizEvalResult:
        """
        사용자의 음성 답변을 채점하고 이유를 설명한다.

        Args:
            question: 퀴즈 문제 텍스트
            options: 보기 목록
            correct_index: 정답 인덱스 (0-based)
            user_answer: 사용자 음성 인식 텍스트

        Returns:
            QuizEvalResult: 정오 여부, 설명
        """
        correct_option = options[correct_index] if 0 <= correct_index < len(options) else ''
        options_text = '\n'.join(f'{i + 1}번. {opt}' for i, opt in enumerate(options))
        prompt = (
            '다음 퀴즈 문제에서 사용자의 음성 답변이 정답인지 평가하세요.\n\n'
            f'문제: {question}\n'
            f'보기:\n{options_text}\n'
            f'정답: {correct_index + 1}번. {correct_option}\n'
            f'사용자 답변: "{user_answer}"\n\n'
            '사용자의 답변이 정답 번호나 정답 내용과 일치하는지 판단하고 이유를 설명하세요.\n'
            '항상 한국어로 답하고, JSON 객체 하나만 반환하세요.\n'
            '반환 형식: {"correct": true 또는 false, "explanation": "한국어 설명 (2~3문장)"}'
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {'role': 'system', 'content': '당신은 JSON만 반환하는 퀴즈 채점 도우미입니다.'},
                    {'role': 'user', 'content': prompt},
                ],
                max_tokens=300,
                temperature=0,
                response_format={'type': 'json_object'},
            )
            raw = (response.choices[0].message.content or '').strip()
            payload = self._parse_json_output(raw)
            return QuizEvalResult(
                correct=bool(payload.get('correct', False)),
                explanation=str(payload.get('explanation', '평가를 생성하지 못했습니다.')).strip(),
                engine=self.model_name,
            )
        except Exception as exc:
            logger.warning('[openai-llm] evaluate_answer failed: %s', exc)
            return QuizEvalResult(
                correct=False,
                explanation='채점 중 오류가 발생했습니다.',
                engine=self.model_name,
            )
