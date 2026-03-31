"""TTS 합성 모듈 — XTTS v2 (로컬) + ElevenLabs (API 폴백)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import torch

from src.base import BaseTTS


# ── 로컬: XTTS v2 (coqui-tts) ───────────────────────────────────────────────

class XTTSEngine(BaseTTS):
    """XTTS v2 기반 로컬 TTS 엔진."""

    _model = None  # 싱글톤

    def _get_model(self):
        if self.__class__._model is None:
            from TTS.api import TTS
            device = 'mps' if torch.backends.mps.is_available() else 'cpu'
            self.__class__._model = TTS('tts_models/multilingual/multi-dataset/xtts_v2').to(device)
        return self.__class__._model

    def synthesize(self, text: str, speaker_wav: str | None = None) -> Path:
        """텍스트를 한국어 음성 파일(.wav)로 합성.

        Args:
            text: 합성할 텍스트
            speaker_wav: 화자 커스터마이징용 레퍼런스 음성 파일 경로 (선택)

        Returns:
            생성된 .wav 파일 경로
        """
        tts = self._get_model()
        output_path = Path(tempfile.mktemp(suffix='.wav'))
        tts.tts_to_file(
            text=text,
            language='ko',
            speaker_wav=speaker_wav,
            file_path=str(output_path),
        )
        return output_path


# ── API 폴백: ElevenLabs ─────────────────────────────────────────────────────

class ElevenLabsTTS(BaseTTS):
    """ElevenLabs Eleven Multilingual v2 기반 API TTS.

    무료 플랜: 월 10,000 크레딧 제공.
    """

    MODEL_ID = 'eleven_multilingual_v2'

    def __init__(self, api_key: str, voice_id: str = 'pNInz6obpgDQGcFmaJgB'):
        import elevenlabs
        self._client = elevenlabs.ElevenLabs(api_key=api_key)
        self._voice_id = voice_id

    def synthesize(self, text: str) -> Path:
        """ElevenLabs API로 텍스트를 음성 파일로 합성."""
        audio = self._client.text_to_speech.convert(
            voice_id=self._voice_id,
            text=text,
            model_id=self.MODEL_ID,
        )
        output_path = Path(tempfile.mktemp(suffix='.wav'))
        with open(output_path, 'wb') as f:
            for chunk in audio:
                f.write(chunk)
        return output_path
