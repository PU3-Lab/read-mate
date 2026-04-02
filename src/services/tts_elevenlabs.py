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
        self._voices_cache: dict[str, str] | None = None

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

        voice_map = self._get_voice_map()
        voice_name, voice_id = self._resolve_voice(voice_preset, voice_map)
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
            voice_name,
            len(text),
            duration,
        )
        return TTSResult(
            audio_path=str(out_path),
            voice_preset=voice_name,
            engine='elevenlabs/eleven_multilingual_v2',
            duration_sec=round(duration, 2),
        )

    def list_presets(self) -> list[str]:
        """사용 가능한 ElevenLabs 계정 화자 목록 반환."""
        return list(self._get_voice_map().keys())

    def _get_voice_map(self) -> dict[str, str]:
        """ElevenLabs API에서 현재 계정의 화자 목록을 동적으로 조회한다."""
        if self._voices_cache is not None:
            return self._voices_cache

        try:
            response = requests.get(
                'https://api.elevenlabs.io/v1/voices',
                headers={'xi-api-key': self.api_key},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise TTSGenerationError(f'ElevenLabs 화자 목록 조회 실패: {exc}') from exc

        voices = payload.get('voices', [])
        voice_map: dict[str, str] = {}
        for voice in voices:
            voice_id = str(voice.get('voice_id') or '').strip()
            voice_name = str(voice.get('name') or '').strip()
            if voice_id and voice_name:
                voice_map[voice_name] = voice_id

        if not voice_map:
            raise TTSGenerationError('ElevenLabs에서 사용 가능한 화자를 찾지 못했습니다.')

        self._voices_cache = dict(sorted(voice_map.items()))
        return self._voices_cache

    @staticmethod
    def _resolve_voice(
        voice_preset: str,
        voice_map: dict[str, str],
    ) -> tuple[str, str]:
        """입력 프리셋을 실제 ElevenLabs 화자 이름/ID로 정규화한다."""
        if voice_preset in voice_map:
            return voice_preset, voice_map[voice_preset]

        for voice_name, voice_id in voice_map.items():
            if voice_preset == voice_id:
                return voice_name, voice_id

        if DEFAULT_VOICE in voice_map:
            return DEFAULT_VOICE, voice_map[DEFAULT_VOICE]

        voice_name = next(iter(voice_map))
        return voice_name, voice_map[voice_name]
