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
import edge_tts

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

class EdgeTTSEngine(BaseTTS):
    _voices_cache: dict[str, str] | None = None

    async def synthesize(self, text: str, voice_preset: str = DEFAULT_VOICE) -> TTSResult:
        if not text.strip():
            raise TTSGenerationError('TTS 입력 텍스트가 비어 있습니다.')

        voice_map = await self._get_voice_map()
        voice_id = self._resolve_voice_id(voice_preset, voice_map)

        TMP_DIR.mkdir(parents=True, exist_ok=True)
        out_path = TMP_DIR / f'{uuid.uuid4().hex}.mp3'

        try:
            t0 = time.perf_counter()
            communicate = edge_tts.Communicate(text, voice_id)
            await communicate.save(str(out_path))
            duration = time.perf_counter() - t0
        except Exception as exc:
            raise TTSGenerationError(f'Edge TTS 합성 실패: {exc}') from exc

        return TTSResult(
            audio_path=str(out_path),
            voice_preset=voice_id,
            engine='edge_tts',
            duration_sec=round(duration, 2),
        )

    @classmethod
    async def _get_voice_map(cls) -> dict[str, str]:
        if cls._voices_cache is not None:
            return cls._voices_cache

        try:
            voices = await edge_tts.list_voices()
        except Exception as exc:
            raise TTSGenerationError(f'Edge TTS 화자 목록 조회 실패: {exc}') from exc

        korean_voices = sorted(
            voice['ShortName']
            for voice in voices
            if voice.get('Locale', '').startswith('ko-')
            and str(voice.get('ShortName', '')).endswith('Neural')
        )

        if not korean_voices:
            raise TTSGenerationError('Edge TTS에서 사용 가능한 한국어 화자를 찾지 못했습니다.')

        cls._voices_cache = {name: name for name in korean_voices}
        return cls._voices_cache

    def list_presets(self) -> list[str]:
        """사용 가능한 Edge TTS 한국어 화자 목록 반환."""
        return list(self._get_voice_map().keys())

    @staticmethod
    def _resolve_voice_id(voice_preset: str, voice_map: dict[str, str]) -> str:
        """입력된 프리셋 이름을 실제 Edge voice id로 정규화한다."""
        if voice_preset in voice_map:
            return voice_map[voice_preset]
        if voice_preset in voice_map.values():
            return voice_preset
        return voice_map.get(DEFAULT_VOICE, next(iter(voice_map.values())))
