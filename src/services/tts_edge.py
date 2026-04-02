"""
Edge TTS 엔진 (Microsoft Edge, 무료 API).
인터넷 연결 필요. API 키 불필요.
한국어 신경망 음성 지원.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid

from core.config import TMP_DIR
from core.exceptions import TTSGenerationError
from models.schemas import TTSResult
from services.base import BaseTTS

logger = logging.getLogger(__name__)

DEFAULT_VOICE = 'ko-KR-SunHiNeural'


def _run_async(coro):
    """동기 메서드에서 async 함수를 안전하게 실행한다."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class EdgeTTSEngine(BaseTTS):
    """
    Microsoft Edge TTS 한국어 엔진.
    상태가 없으므로 싱글톤 불필요.
    인터넷 연결이 필요하며 API 키는 불필요하다.
    """

    _voices_cache: dict[str, str] | None = None

    def synthesize(self, text: str, voice_preset: str = DEFAULT_VOICE) -> TTSResult:
        """
        텍스트를 Edge TTS로 음성 합성한다.

        Args:
            text: 읽어줄 텍스트
            voice_preset: 프리셋 목소리 이름 (EDGE_VOICES 키)

        Returns:
            TTSResult: 오디오 파일 경로, 목소리, 엔진명, 재생 시간

        Raises:
            TTSGenerationError: API 호출 실패 시
        """
        import edge_tts

        if not text.strip():
            raise TTSGenerationError('TTS 입력 텍스트가 비어 있습니다.')

        voice_map = self._get_voice_map()
        voice_id = self._resolve_voice_id(voice_preset, voice_map)
        out_path = TMP_DIR / f'{uuid.uuid4().hex}.mp3'

        async def _synthesize() -> None:
            communicate = edge_tts.Communicate(text, voice_id)
            await communicate.save(str(out_path))

        try:
            t0 = time.perf_counter()
            _run_async(_synthesize())
            duration = time.perf_counter() - t0
        except Exception as exc:
            raise TTSGenerationError(f'Edge TTS 합성 실패: {exc}') from exc

        logger.info(
            '[tts:edge] voice=%s chars=%d elapsed=%.2fs',
            voice_id,
            len(text),
            duration,
        )
        return TTSResult(
            audio_path=str(out_path),
            voice_preset=voice_id,
            engine='edge_tts',
            duration_sec=round(duration, 2),
        )

    def list_presets(self) -> list[str]:
        """사용 가능한 Edge TTS 한국어 화자 목록 반환."""
        return list(self._get_voice_map().keys())

    @classmethod
    def _get_voice_map(cls) -> dict[str, str]:
        """Edge TTS에서 실제 사용 가능한 한국어 화자를 동적으로 조회한다."""
        if cls._voices_cache is not None:
            return cls._voices_cache

        import edge_tts

        async def _load_voices() -> dict[str, str]:
            voices = await edge_tts.list_voices()
            korean_voices = sorted(
                voice['ShortName']
                for voice in voices
                if voice.get('Locale', '').startswith('ko-')
                and str(voice.get('ShortName', '')).endswith('Neural')
            )
            return {name: name for name in korean_voices}

        try:
            voice_map = _run_async(_load_voices())
        except Exception as exc:
            raise TTSGenerationError(f'Edge TTS 화자 목록 조회 실패: {exc}') from exc

        if not voice_map:
            raise TTSGenerationError('Edge TTS에서 사용 가능한 한국어 화자를 찾지 못했습니다.')

        cls._voices_cache = voice_map
        return voice_map

    @staticmethod
    def _resolve_voice_id(voice_preset: str, voice_map: dict[str, str]) -> str:
        """입력된 프리셋 이름을 실제 Edge voice id로 정규화한다."""
        if voice_preset in voice_map:
            return voice_map[voice_preset]
        if voice_preset in voice_map.values():
            return voice_preset
        return voice_map.get(DEFAULT_VOICE, next(iter(voice_map.values())))
