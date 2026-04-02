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

# 한국어 Edge TTS 화자 목록
EDGE_VOICES: dict[str, str] = {
    'SunHi': 'ko-KR-SunHiNeural',      # 여성, 밝고 자연스러운 톤
    'InJoon': 'ko-KR-InJoonNeural',     # 남성, 안정적인 톤
    'BongJin': 'ko-KR-BongJinNeural',   # 남성, 뉴스 아나운서 스타일
    'GookMin': 'ko-KR-GookMinNeural',   # 남성, 차분한 톤
    'JiMin': 'ko-KR-JiMinNeural',       # 여성, 친근한 톤
    'YuJin': 'ko-KR-YuJinNeural',       # 여성, 부드러운 톤
    'Hyunsu': 'ko-KR-HyunsuMultilingualNeural',  # 남성, 다국어
}
DEFAULT_VOICE = 'SunHi'


class EdgeTTSEngine(BaseTTS):
    """
    Microsoft Edge TTS 한국어 엔진.
    상태가 없으므로 싱글톤 불필요.
    인터넷 연결이 필요하며 API 키는 불필요하다.
    """

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

        voice_id = EDGE_VOICES.get(
            voice_preset, EDGE_VOICES[DEFAULT_VOICE]
        )
        out_path = TMP_DIR / f'{uuid.uuid4().hex}.mp3'

        async def _synthesize() -> None:
            communicate = edge_tts.Communicate(text, voice_id)
            await communicate.save(str(out_path))

        try:
            t0 = time.perf_counter()
            asyncio.run(_synthesize())
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
            voice_preset=voice_preset,
            engine='edge_tts',
            duration_sec=round(duration, 2),
        )

    def list_presets(self) -> list[str]:
        """사용 가능한 Edge TTS 한국어 화자 목록 반환."""
        return list(EDGE_VOICES.keys())
