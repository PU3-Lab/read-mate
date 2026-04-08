"""
LLM 엔진 팩토리.
LLM_ENGINE 환경변수로 엔진을 선택한다: gemma (기본) | qwen | openai
"""

from __future__ import annotations

import importlib
import logging

from core.config import LLM_ENGINE
from services.base import BaseLLM

logger = logging.getLogger(__name__)

_ENGINE_MAP = {
    'gemma': 'services.llm_gemma.GemmaLLM',
    'qwen': 'services.llm_qwen.QwenLLM',
    'openai': 'services.llm_openai.OpenAILLM',
}


def create_llm() -> BaseLLM:
    """
    LLM_ENGINE 환경변수에 따라 LLM 인스턴스를 생성한다.

    Returns:
        BaseLLM: 선택된 LLM 엔진 인스턴스
    """
    engine_key = LLM_ENGINE.lower()
    class_path = _ENGINE_MAP.get(engine_key)
    if class_path is None:
        raise ValueError(
            f'알 수 없는 LLM_ENGINE: "{engine_key}". '
            f'허용값: {list(_ENGINE_MAP.keys())}'
        )

    module_path, class_name = class_path.rsplit('.', 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)

    logger.info('[llm-factory] engine=%s class=%s', engine_key, class_name)
    return cls()
