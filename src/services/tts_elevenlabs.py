"""
ElevenLabs API 폴백 TTS 엔진.
"""

from __future__ import annotations

import logging
import time
import uuid

import requests

from core.config import ELEVENLABS_API_KEY, TMP_DIR
from core.exceptions import TTSGenerationError
from models.schemas import TTSResult
from services.base import BaseTTS

logger = logging.getLogger(__name__)

ELEVENLABS_VOICES: dict[str, str] = {
    'Rachel': '21m00Tcm4TlvDq8ikWAM',
    'Domi': 'AZnzlk1XvdvUeBnXmlld',
    'Bella': 'EXAVITQu4vr4xnSDxMaL',
    'Antoni': 'ErXwobaYiN019PkySvjV',
    'Elli': 'MF3mGyEYCl7XYWbV9V6O',
}
DEFAULT_VOICE = 'Rachel'
ELEVENLABS_MODEL = 'eleven_multilingual_v2'


class ElevenLabsTTS(BaseTTS):
    """ElevenLabs Eleven Multilingual v2 API 폴백 TTS 엔진."""

    def __init__(self, api_key: str = ELEVENLABS_API_KEY) -> None:
        """
        ElevenLabs TTS 엔진을 초기화한다.

        Args:
            api_key: ElevenLabs API 키

        Raises:
            ValueError: API 키 미설정 시
        """
        if not api_key:
            raise ValueError('ELEVENLABS_API_KEY가 .env에 설정되어 있지 않습니다.')
        self.api_key = api_key

    def synthesize(self, text: str, voice_preset: str = DEFAULT_VOICE) -> TTSResult:
        """
        텍스트를 ElevenLabs API로 음성 합성한다.

        Args:
            text: 읽어줄 텍스트
            voice_preset: 프리셋 목소리 이름

        Returns:
            TTSResult: 오디오 파일 경로, 목소리, 엔진명, 재생 시간

        Raises:
            TTSGenerationError: API 호출 실패 시
        """
        if not text.strip():
            raise TTSGenerationError('TTS 입력 텍스트가 비어 있습니다.')

        voice_id = ELEVENLABS_VOICES.get(voice_preset, ELEVENLABS_VOICES[DEFAULT_VOICE])
        url = f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}'

        try:
            t0 = time.perf_counter()
            response = requests.post(
                url,
                headers={
                    'xi-api-key': self.api_key,
                    'Content-Type': 'application/json',
                },
                json={
                    'text': text,
                    'model_id': ELEVENLABS_MODEL,
                    'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75},
                },
                timeout=60,
            )
            response.raise_for_status()
            duration = time.perf_counter() - t0
        except Exception as exc:
            raise TTSGenerationError(f'ElevenLabs API 호출 실패: {exc}') from exc

        out_path = TMP_DIR / f'{uuid.uuid4().hex}.mp3'
        out_path.write_bytes(response.content)

        logger.info(
            '[tts:elevenlabs] voice=%s chars=%d elapsed=%.2fs',
            voice_preset,
            len(text),
            duration,
        )
        return TTSResult(
            audio_path=str(out_path),
            voice_preset=voice_preset,
            engine='elevenlabs/eleven_multilingual_v2',
            duration_sec=round(duration, 2),
        )

    def list_presets(self) -> list[str]:
        """사용 가능한 ElevenLabs 프리셋 목소리 목록 반환."""
        return list(ELEVENLABS_VOICES.keys())
