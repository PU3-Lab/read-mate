"""
LLM 엔진 팩토리.
LLM_ENGINE 환경변수로 엔진을 선택한다: gemma (기본) | qwen | openai
"""

from __future__ import annotations

import logging
import os

from services.base import BaseLLM

logger = logging.getLogger(__name__)

_ENGINE_MAP = {
    'gemma': 'services.llm_gemma.GemmaLLM',
    'qwen': 'services.llm_qwen.QwenLLM',
    'openai': 'services.llm_openai.OpenAILLM',
}

_instance: BaseLLM | None = None


def get_llm() -> BaseLLM:
    """
    LLM_ENGINE 환경변수에 따라 LLM 싱글톤을 반환한다.

    Returns:
        BaseLLM: 선택된 LLM 엔진 인스턴스
    """
    global _instance
    if _instance is not None:
        return _instance

    engine_key = os.getenv('LLM_ENGINE', 'gemma').lower()
    class_path = _ENGINE_MAP.get(engine_key)
    if class_path is None:
        raise ValueError(
            f'알 수 없는 LLM_ENGINE: "{engine_key}". '
            f'허용값: {list(_ENGINE_MAP.keys())}'
        )

    module_path, class_name = class_path.rsplit('.', 1)
    import importlib
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)

    logger.info('[llm-factory] engine=%s class=%s', engine_key, class_name)
    _instance = cls()
    return _instance
