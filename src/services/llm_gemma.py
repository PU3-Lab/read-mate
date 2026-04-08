"""
ReadMate용 Gemma 기반 LLM 서비스 구현체.
요약과 질의응답을 JSON 포맷으로 강제하고, 파싱 실패 시 재시도한다.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoProcessor

from core.config import (
    LLM_MAX_INPUT_CHARS,
    LLM_MAX_NEW_TOKENS,
    LLM_MAX_RETRIES,
    LLM_MODEL_DEFAULT,
)
from lib.utils.device import available_device
from models.schemas import LLMResult, QuizEvalResult, QuizItem, TaskType
from services.llm_base import ChunkedLLM

logger = logging.getLogger(__name__)


class GemmaLLM(ChunkedLLM):
    """Gemma4 기반 ReadMate LLM 서비스."""

    _shared_model: AutoModelForCausalLM | None = None
    _shared_processor: AutoProcessor | None = None
    _shared_model_name: str | None = None

    def __init__(
        self,
        model_name: str = LLM_MODEL_DEFAULT,
        max_input_chars: int = LLM_MAX_INPUT_CHARS,
        max_new_tokens: int = LLM_MAX_NEW_TOKENS,
    ) -> None:
        """
        Gemma LLM 서비스를 초기화한다.

        Args:
            model_name: Hugging Face 모델 이름 또는 로컬 경로
            max_input_chars: 프롬프트에 포함할 최대 본문 길이
            max_new_tokens: 생성 최대 토큰 수
        """
        self.model_name = model_name
        self.max_input_chars = max_input_chars
        self.max_new_tokens = max_new_tokens
        self.device = available_device()
        self.dtype = self._resolve_dtype(self.device)
        self.processor, self.model = self._get_or_load_model()

    def _generate_single(
        self, text: str, task: TaskType, question: str | None
    ) -> LLMResult:
        """
        단일 청크 텍스트에 대해 추론을 실행한다.

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
                    '[llm:gemma] parse/inference retry=%s/%s failed: %s',
                    attempt,
                    LLM_MAX_RETRIES,
                    exc,
                )

        logger.error('[llm:gemma] all retries failed: %s', last_error)
        return self._build_fallback_result(task, question)

    @classmethod
    def _resolve_dtype(cls, device: str) -> torch.dtype:
        """
        디바이스에 맞는 dtype을 결정한다.

        Args:
            device: 추론 디바이스 이름

        Returns:
            torch.dtype: 추론용 dtype
        """
        if device == 'cpu':
            return torch.float32
        return torch.bfloat16

    def _get_or_load_model(
        self,
    ) -> tuple[AutoProcessor, AutoModelForCausalLM]:
        """
        프로세서와 모델을 싱글톤으로 로드한다.

        Returns:
            tuple[AutoProcessor, AutoModelForCausalLM]: 재사용 가능한 모델 객체
        """
        if (
            self.__class__._shared_model is not None
            and self.__class__._shared_processor is not None
            and self.__class__._shared_model_name == self.model_name
        ):
            return self.__class__._shared_processor, self.__class__._shared_model

        logger.info(
            '[llm:gemma] loading model=%s device=%s dtype=%s',
            self.model_name,
            self.device,
            self.dtype,
        )

        processor = AutoProcessor.from_pretrained(
            self.model_name,
            trust_remote_code=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            dtype=self.dtype,
            trust_remote_code=True,
        )
        model.to(self.device)
        model.eval()

        self.__class__._shared_processor = processor
        self.__class__._shared_model = model
        self.__class__._shared_model_name = self.model_name
        return processor, model

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

        retry_instruction = ''
        if attempt > 1:
            retry_instruction = (
                '\n이전 응답은 JSON 파싱에 실패했습니다. '
                '설명문 없이 JSON 객체 하나만 반환하세요.'
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
            '- QUIZ이면 quiz 필드에 반드시 10개의 문제를 작성합니다.\n'
            '- QUIZ가 아니면 quiz는 null로 둡니다.\n'
            f'- 작업 지시: {task_instruction}{retry_instruction}\n\n'
            f'본문:\n{text}\n'
            f'{question_block}\n'
        )

    def _run_inference(self, prompt: str) -> str:
        """
        모델 추론을 실행하고 생성 텍스트를 반환한다.

        Args:
            prompt: 모델 입력 프롬프트

        Returns:
            str: 생성된 원문 텍스트
        """
        messages = [
            {
                'role': 'system',
                'content': [{'type': 'text', 'text': '당신은 JSON만 반환하는 정확한 도우미입니다.'}],
            },
            {
                'role': 'user',
                'content': [{'type': 'text', 'text': prompt}],
            },
        ]
        encoded = self.processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors='pt',
        )
        encoded = {key: value.to(self.device) for key, value in encoded.items()}
        input_len = encoded['input_ids'].shape[-1]

        with torch.inference_mode():
            output = self.model.generate(
                **encoded,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
                pad_token_id=self.processor.tokenizer.eos_token_id,
                eos_token_id=self.processor.tokenizer.eos_token_id,
            )

        generated_tokens = output[0][input_len:]
        return self.processor.decode(generated_tokens, skip_special_tokens=True).strip()

    def _sanitize_json(self, text: str) -> str:
        """
        Gemma 출력의 흔한 JSON 오류를 수정한다.

        처리 항목:
        - 마크다운 코드 블록 제거 (```json ... ```)
        - 중괄호 블록 추출
        - Python 리터럴 변환 (None→null, True→true, False→false)
        - 후행 쉼표 제거 (, } / , ])
        - 작은따옴표 → 큰따옴표
        """
        # 마크다운 코드 블록 제거
        text = re.sub(r'```(?:json)?\s*', '', text)
        text = re.sub(r'```', '', text).strip()

        # 중괄호 블록 추출
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            text = match.group(0)

        # Python 리터럴 → JSON 리터럴
        text = re.sub(r'\bNone\b', 'null', text)
        text = re.sub(r'\bTrue\b', 'true', text)
        text = re.sub(r'\bFalse\b', 'false', text)

        # 후행 쉼표 제거
        text = re.sub(r',\s*([\}\]])', r'\1', text)

        # 작은따옴표 → 큰따옴표 (키·값 모두)
        text = re.sub(r"'([^']*)'", r'"\1"', text)

        return text

    def _parse_json_output(self, raw_output: str) -> dict[str, Any]:
        """
        모델 출력에서 JSON 객체를 추출해 파싱한다.
        파싱 실패 시 _sanitize_json으로 정제 후 재시도한다.

        Args:
            raw_output: 모델이 생성한 텍스트

        Returns:
            dict[str, Any]: 파싱된 JSON 딕셔너리
        """
        for candidate in (raw_output, self._sanitize_json(raw_output)):
            try:
                payload = json.loads(candidate)
                if isinstance(payload, dict):
                    return payload
            except json.JSONDecodeError:
                continue

        raise ValueError('JSON 객체를 파싱하지 못했습니다.')

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
        """사용자의 음성 답변을 채점하고 이유를 설명한다."""
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
            raw = self._run_inference(prompt)
            payload = self._parse_json_output(raw)
            return QuizEvalResult(
                correct=bool(payload.get('correct', False)),
                explanation=str(payload.get('explanation', '평가를 생성하지 못했습니다.')).strip(),
                engine=self.model_name,
            )
        except Exception as exc:
            logger.warning('[llm:gemma] evaluate_answer failed: %s', exc)
            return QuizEvalResult(
                correct=False,
                explanation='채점 중 오류가 발생했습니다.',
                engine=self.model_name,
            )
