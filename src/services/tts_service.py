"""
TTS 서비스.
TTSFactory를 통해 엔진을 가져와 합성·프리셋 조회를 제공한다.
"""

from __future__ import annotations

from models.schemas import TTSResult
from services.base import BaseTTS
from services.tts_factory import EngineType, TTSFactory


class TTSService:
    """
    TTS 서비스.
    engine으로 사용할 엔진을 지정한다.

    지원 엔진:
        'kokoro'     - Kokoro ONNX 로컬 (영어 화자, 한국어 텍스트 처리 불완전)
        'mms'        - Meta MMS-TTS 로컬 (한국어 전용, 단일 화자)
        'edge'       - Microsoft Edge TTS (한국어 최상급 품질, 인터넷 필요)
        'elevenlabs' - ElevenLabs API (다국어, API 키 필요)
    """

    def __init__(self, engine: EngineType = 'mms') -> None:
        self._engine: BaseTTS = TTSFactory().get(engine)

    def synthesize(self, text: str, voice_preset: str = '') -> TTSResult:
        """
        텍스트를 음성으로 합성한다.

        Args:
            text: 읽어줄 텍스트
            voice_preset: 목소리 프리셋 이름 (빈 문자열이면 엔진 기본값 사용)

        Returns:
            TTSResult: 오디오 파일 경로, 목소리, 엔진명, 재생 시간
        """
        return self._engine.synthesize(text, voice_preset)

    def list_presets(self) -> list[str]:
        """사용 가능한 목소리 프리셋 목록 반환."""
        return self._engine.list_presets()

    @staticmethod
    def available_engines() -> list[str]:
        """사용 가능한 엔진 이름 목록 반환."""
        return TTSFactory.available()
