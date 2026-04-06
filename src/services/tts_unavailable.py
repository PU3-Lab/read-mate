"""
TTS 의존성 또는 모델 초기화 실패 시 사용하는 대체 구현체.
앱 전체는 계속 동작하고, TTS 단계에서만 경고를 남긴다.
"""

from __future__ import annotations

from core.exceptions import TTSGenerationError
from models.schemas import TTSResult
from services.base import BaseTTS


class UnavailableTTSEngine(BaseTTS):
    """사용 불가능한 TTS 상태를 표현하는 엔진."""

    def __init__(self, reason: str) -> None:
        """
        Args:
            reason: TTS를 사용할 수 없는 이유
        """
        self.reason = reason

    def synthesize(self, text: str, voice_preset: str = 'default') -> TTSResult:
        """
        항상 실패를 발생시켜 상위 파이프라인이 경고로 처리하게 한다.
        """
        raise TTSGenerationError(self.reason)

    def list_presets(self) -> list[str]:
        """사용 가능한 프리셋이 없으므로 빈 목록을 반환한다."""
        return []
