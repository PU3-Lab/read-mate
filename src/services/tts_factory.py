"""
TTS 엔진 팩토리.
엔진 교체·추가 시 _REGISTRY만 수정한다.
"""

from __future__ import annotations

from typing import Literal

from services.base import BaseTTS

EngineType = Literal['kokoro', 'mms', 'edge', 'elevenlabs', 'zonos']

# 엔진 이름 → 클래스 매핑 (지연 임포트로 미사용 엔진 로드 방지)
_REGISTRY: dict[str, str] = {
    'kokoro':     'services.tts_kokoro.KokoroEngine',
    'mms':        'services.tts_mms.MMSEngine',
    'edge':       'services.tts_edge.EdgeTTSEngine',
    'elevenlabs': 'services.tts_elevenlabs.ElevenLabsTTS',
    'zonos':      'services.tts_zonos.ZonosEngine',
}


def _import(dotted: str) -> type:
    """'패키지.모듈.클래스' 문자열을 클래스 객체로 반환한다."""
    module_path, cls_name = dotted.rsplit('.', 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, cls_name)


class TTSFactory:
    """TTS 엔진 인스턴스를 생성하는 팩토리."""

    def get(self, engine: EngineType) -> BaseTTS:
        """
        엔진 이름으로 TTS 엔진 인스턴스를 반환한다.

        Args:
            engine: 'kokoro' | 'mms' | 'edge' | 'elevenlabs' | 'zonos'

        Returns:
            BaseTTS 구현체

        Raises:
            ValueError: 알 수 없는 엔진 이름
        """
        if engine not in _REGISTRY:
            raise ValueError(
                f'알 수 없는 TTS 엔진: {engine!r}. '
                f'사용 가능: {list(_REGISTRY)}'
            )
        cls = _import(_REGISTRY[engine])
        return cls()

    @staticmethod
    def available() -> list[str]:
        """등록된 엔진 이름 목록 반환."""
        return list(_REGISTRY)
