"""
Kokoro ONNX 로컬 TTS 엔진.
"""

from __future__ import annotations

import logging
import time
import urllib.request
import uuid
from pathlib import Path

import soundfile as sf

from core.config import MODEL_DIR, TMP_DIR
from core.exceptions import TTSGenerationError
from models.schemas import TTSResult
from services.base import BaseTTS

logger = logging.getLogger(__name__)

_RELEASE_BASE = (
    'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0'
)
_MODEL_FILENAME = 'kokoro-v1.0.onnx'
_VOICES_FILENAME = 'voices-v1.0.bin'

# 한국어 화자 우선, 없으면 영어 기본 화자로 폴백
_PREFERRED_LANG_PREFIX = 'kf_', 'km_'
_FALLBACK_VOICE = 'af_bella'


def _download_if_missing(filename: str, dest_dir: Path) -> Path:
    """파일이 없을 때만 GitHub releases에서 다운로드한다."""
    dest = dest_dir / filename
    if dest.exists():
        return dest
    url = f'{_RELEASE_BASE}/{filename}'
    logger.info('[tts] 다운로드 중: %s → %s', url, dest)
    urllib.request.urlretrieve(url, dest)  # noqa: S310
    return dest


class KokoroEngine(BaseTTS):
    """
    Kokoro ONNX 기반 로컬 TTS 엔진.
    모델은 싱글톤으로 유지하며 첫 사용 시 자동 다운로드한다.
    """

    _instance: KokoroEngine | None = None
    _model = None

    def __new__(cls) -> KokoroEngine:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._model is not None:
            return
        from kokoro_onnx import Kokoro

        kokoro_dir = MODEL_DIR / 'kokoro'
        kokoro_dir.mkdir(parents=True, exist_ok=True)

        model_path = _download_if_missing(_MODEL_FILENAME, kokoro_dir)
        voices_path = _download_if_missing(_VOICES_FILENAME, kokoro_dir)

        logger.info('[tts] Kokoro ONNX 로딩...')
        self._kokoro = Kokoro(str(model_path), str(voices_path))
        self._voices: list[str] = self._kokoro.get_voices()
        self._default_voice = self._pick_default_voice()
        self._model = True
        logger.info(
            '[tts] Kokoro ONNX 로딩 완료 (voices=%d, default=%s)',
            len(self._voices),
            self._default_voice,
        )

    def _pick_default_voice(self) -> str:
        """한국어 화자가 있으면 첫 번째를 반환, 없으면 폴백 사용."""
        for prefix in _PREFERRED_LANG_PREFIX:
            matches = [v for v in self._voices if v.startswith(prefix)]
            if matches:
                return matches[0]
        return _FALLBACK_VOICE if _FALLBACK_VOICE in self._voices else self._voices[0]

    def synthesize(self, text: str, voice_preset: str = '') -> TTSResult:
        """
        텍스트를 Kokoro ONNX로 음성 합성한다.

        Args:
            text: 읽어줄 텍스트
            voice_preset: 프리셋 목소리 이름 (빈 문자열이면 기본값 사용)

        Returns:
            TTSResult: 오디오 파일 경로, 목소리, 엔진명, 재생 시간

        Raises:
            TTSGenerationError: 합성 실패 시
        """
        if not text.strip():
            raise TTSGenerationError('TTS 입력 텍스트가 비어 있습니다.')

        voice = (
            voice_preset
            if voice_preset and voice_preset in self._voices
            else self._default_voice
        )
        # 한국어 화자가 있으면 ko, 없으면 en-us
        lang = 'ko' if voice.startswith(('kf_', 'km_')) else 'en-us'
        out_path = TMP_DIR / f'{uuid.uuid4().hex}.wav'

        try:
            t0 = time.perf_counter()
            samples, sample_rate = self._kokoro.create(
                text=text,
                voice=voice,
                speed=1.0,
                lang=lang,
            )
            sf.write(str(out_path), samples, sample_rate)
            duration = time.perf_counter() - t0
        except Exception as exc:
            raise TTSGenerationError(f'Kokoro 합성 실패: {exc}') from exc

        logger.info(
            '[tts:kokoro] voice=%s lang=%s chars=%d elapsed=%.2fs',
            voice,
            lang,
            len(text),
            duration,
        )
        return TTSResult(
            audio_path=str(out_path),
            voice_preset=voice,
            engine='kokoro_onnx',
            duration_sec=round(duration, 2),
        )

    def list_presets(self) -> list[str]:
        """사용 가능한 Kokoro 목소리 목록 반환."""
        return self._voices.copy()
