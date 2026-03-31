"""LLM 분석 모듈 — Qwen2.5-7B (로컬) + OpenAI (API 폴백)."""

from __future__ import annotations

import json
import re

import torch

from src.base import BaseLLM

MAX_RETRIES = 3


# ── 로컬: Qwen2.5-7B-Instruct ────────────────────────────────────────────────


class QwenLLM(BaseLLM):
    """Qwen2.5-7B-Instruct 기반 로컬 LLM."""

    MODEL_ID = 'Qwen/Qwen2.5-7B-Instruct'
    _model = None
    _tokenizer = None  # 싱글톤

    def _get_model(self):
        if self.__class__._model is None:
            from transformers import AutoModelForCausalLM, AutoTokenizer

            device = 'mps' if torch.backends.mps.is_available() else 'cpu'
            self.__class__._tokenizer = AutoTokenizer.from_pretrained(self.MODEL_ID)
            self.__class__._model = AutoModelForCausalLM.from_pretrained(
                self.MODEL_ID,
                torch_dtype=torch.bfloat16,
                device_map=device,
            )
        return self.__class__._model, self.__class__._tokenizer

    def analyze(self, text: str) -> dict:
        """Qwen2.5로 텍스트 분석, JSON 반환 (최대 3회 재시도)."""
        for attempt in range(MAX_RETRIES):
            try:
                raw = self._generate(text)
                return _parse_json(raw)
            except (json.JSONDecodeError, KeyError):
                if attempt == MAX_RETRIES - 1:
                    raise ValueError(f'LLM JSON 파싱 실패 ({MAX_RETRIES}회 시도)')
        return {}

    def _generate(self, text: str) -> str:
        model, tokenizer = self._get_model()
        prompt = _build_prompt(text)
        inputs = tokenizer(prompt, return_tensors='pt').to(model.device)
        with torch.no_grad():
            outputs = model.generate(**inputs, max_new_tokens=1024, do_sample=False)
        return tokenizer.decode(
            outputs[0][inputs['input_ids'].shape[1] :], skip_special_tokens=True
        )


# ── API 폴백: OpenAI GPT-5.4-mini ────────────────────────────────────────────


class OpenAILLM(BaseLLM):
    """OpenAI GPT-5.4-mini 기반 API LLM."""

    MODEL = 'gpt-5.4-mini'

    def __init__(self, api_key: str):
        import openai

        self._client = openai.OpenAI(api_key=api_key)

    def analyze(self, text: str) -> dict:
        """GPT-5.4-mini로 텍스트 분석, JSON 반환."""
        for attempt in range(MAX_RETRIES):
            try:
                response = self._client.chat.completions.create(
                    model=self.MODEL,
                    messages=[{'role': 'user', 'content': _build_prompt(text)}],
                    response_format={'type': 'json_object'},
                )
                return json.loads(response.choices[0].message.content)
            except (json.JSONDecodeError, KeyError):
                if attempt == MAX_RETRIES - 1:
                    raise ValueError(f'LLM JSON 파싱 실패 ({MAX_RETRIES}회 시도)')
        return {}


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────


def _build_prompt(text: str) -> str:
    """분석 프롬프트 생성."""
    return f"""다음 텍스트를 분석하고 아래 JSON 형식으로만 응답하세요.
            텍스트:
            {text}

            응답 형식:
            {{
            "summary": "핵심 내용 3~5문장 요약",
            "quiz": [
                {{
                "question": "문제",
                "options": ["①보기1", "②보기2", "③보기3", "④보기4"],
                "answer": 0
                }}
            ],
            "keywords": ["키워드1", "키워드2", "키워드3"],
            "simple_explanation": "어려운 개념을 쉽게 재설명"
            }}"""


def _parse_json(raw: str) -> dict:
    """LLM 출력에서 JSON 추출 및 파싱."""
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        raise json.JSONDecodeError('JSON 블록 없음', raw, 0)
    return json.loads(match.group())
