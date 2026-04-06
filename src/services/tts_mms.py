"""
MMS-TTS 로컬 TTS 엔진 (Meta, facebook/mms-tts-kor).
transformers VitsModel 사용, 추가 의존성 없음.
단일 화자(한국어 전용).
"""

from __future__ import annotations

import logging
import time
import uuid

import soundfile as sf
import torch

from core.config import TMP_DIR
from core.exceptions import TTSGenerationError
from lib.utils.device import available_device
from models.schemas import TTSResult
from services.base import BaseTTS

logger = logging.getLogger(__name__)

_MMS_MODEL_ID = 'facebook/mms-tts-kor'
_PRESET = 'default'


class MMSEngine(BaseTTS):
    """
    Meta MMS-TTS 한국어 엔진.
    싱글톤으로 유지하며 첫 사용 시 HuggingFace에서 자동 다운로드한다.
    단일 화자이므로 voice_preset은 무시된다.
    """

    _instance: MMSEngine | None = None
    _model = None

    def __new__(cls) -> MMSEngine:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._model is not None:
            return
        from transformers import AutoTokenizer, VitsModel

        device = available_device()
        logger.info('[tts] MMS-TTS 로딩 model=%s device=%s', _MMS_MODEL_ID, device)
        self._tokenizer = AutoTokenizer.from_pretrained(_MMS_MODEL_ID)
        # VitsModel은 float32로 추론 (bfloat16 미지원)
        self._model = VitsModel.from_pretrained(_MMS_MODEL_ID).to(device)
        self._device = device
        self._sample_rate: int = self._model.config.sampling_rate
        logger.info('[tts] MMS-TTS 로딩 완료 (sample_rate=%d)', self._sample_rate)

    def synthesize(self, text: str, voice_preset: str = _PRESET) -> TTSResult:
        """
        텍스트를 MMS-TTS로 음성 합성한다.

        Args:
            text: 읽어줄 텍스트 (한국어)
            voice_preset: 무시됨 (단일 화자)

        Returns:
            TTSResult: 오디오 파일 경로, 목소리, 엔진명, 재생 시간

        Raises:
            TTSGenerationError: 합성 실패 시
        """
        if not text.strip():
            raise TTSGenerationError('TTS 입력 텍스트가 비어 있습니다.')

        out_path = TMP_DIR / f'{uuid.uuid4().hex}.wav'

        try:
            t0 = time.perf_counter()
            inputs = self._tokenizer(text, return_tensors='pt').to(self._device)
            with torch.no_grad():
                waveform = (
                    self._model(**inputs).waveform.squeeze().cpu().float().numpy()
                )
            sf.write(str(out_path), waveform, self._sample_rate)
            duration = time.perf_counter() - t0
        except Exception as exc:
            raise TTSGenerationError(f'MMS-TTS 합성 실패: {exc}') from exc

        logger.info(
            '[tts:mms] chars=%d elapsed=%.2fs', len(text), duration
        )
        return TTSResult(
            audio_path=str(out_path),
            voice_preset=_PRESET,
            engine='mms_tts_kor',
            duration_sec=round(duration, 2),
        )

    def list_presets(self) -> list[str]:
        """MMS-TTS는 단일 화자다."""
        return [_PRESET]
