"""
ReadMate STT 서비스 구현체.
- FasterWhisperEngine: faster-whisper 기반 로컬 STT 엔진 (싱글톤 모델)
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from core.config import STT_MODEL, TMP_DIR
from core.exceptions import STTError
from lib.utils.device import available_device
from models.schemas import STTResult, STTSegment
from services.base import BaseSTT

logger = logging.getLogger(__name__)


class FasterWhisperEngine(BaseSTT):
    """
    faster-whisper 기반 로컬 STT 엔진.
    모델은 싱글톤으로 유지한다.
    Mac MPS는 faster-whisper가 지원하지 않으므로 cpu로 폴백한다.
    """

    _instance: FasterWhisperEngine | None = None
    _model = None

    def __new__(cls, model_size: str = STT_MODEL) -> FasterWhisperEngine:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, model_size: str = STT_MODEL) -> None:
        if self._model is not None:
            return
        from faster_whisper import WhisperModel

        device = self._resolve_device()
        compute_type = 'float32' if device == 'cpu' else 'bfloat16'

        logger.info(
            '[stt] FasterWhisper loading model=%s device=%s compute=%s',
            model_size,
            device,
            compute_type,
        )
        self._model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
        )
        self._model_size = model_size

    def transcribe(self, audio_bytes: bytes) -> STTResult:
        """
        오디오 바이트를 텍스트로 변환한다.

        Args:
            audio_bytes: 오디오 원본 바이트 (.mp3 / .wav 등)

        Returns:
            STTResult: 전체 텍스트, 언어, 세그먼트 목록, 엔진명

        Raises:
            STTError: 변환 실패 시
        """
        tmp_path = TMP_DIR / f'{uuid.uuid4().hex}.audio'
        try:
            tmp_path.write_bytes(audio_bytes)
            return self._run_transcribe(tmp_path)
        except STTError:
            raise
        except Exception as exc:
            raise STTError(f'STT 변환 실패: {exc}') from exc
        finally:
            tmp_path.unlink(missing_ok=True)

    def _run_transcribe(self, audio_path: Path) -> STTResult:
        """
        실제 faster-whisper 추론을 실행한다.

        Args:
            audio_path: 임시 오디오 파일 경로

        Returns:
            STTResult: 변환 결과
        """
        segments_iter, info = self._model.transcribe(
            str(audio_path),
            beam_size=5,
            language=None,  # 자동 감지
            vad_filter=True,  # 묵음 구간 제거
        )

        segments: list[STTSegment] = []
        for seg in segments_iter:
            segments.append(
                STTSegment(
                    start=round(seg.start, 2),
                    end=round(seg.end, 2),
                    text=seg.text.strip(),
                )
            )

        full_text = ' '.join(s.text for s in segments if s.text)
        language = info.language

        logger.info(
            '[stt] model=%s lang=%s segments=%d chars=%d',
            self._model_size,
            language,
            len(segments),
            len(full_text),
        )

        return STTResult(
            text=full_text,
            language=language,
            segments=segments,
            engine=f'faster-whisper/{self._model_size}',
        )

    @staticmethod
    def _resolve_device() -> str:
        """
        faster-whisper 지원 디바이스를 결정한다.
        MPS는 지원하지 않으므로 cpu로 폴백한다.

        Returns:
            str: 'cuda' 또는 'cpu'
        """
        device = available_device()
        if device == 'mps':
            logger.info('[stt] MPS 미지원 → cpu 폴백')
            return 'cpu'
        return device
