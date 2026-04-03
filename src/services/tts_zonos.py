"""
ReadMate Zonos TTS 서비스 구현체.
Zyphra의 Zonos 모델을 사용하여 고성능 TTS와 세밀한 음성 조절을 제공한다.
"""

from __future__ import annotations

import logging
import math
import re
import shutil
import sys
import time
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

from core.config import EMBEDDINGS_DIR, TMP_DIR, VOICES_DIR, ZONOS_MODEL
from core.exceptions import TTSGenerationError
from lib.utils.device import available_device
from models.schemas import TTSResult
from services.base import BaseTTS
from zonos.model import Zonos

logger = logging.getLogger(__name__)


class ZonosTTSEngine(BaseTTS):
    """
    Zonos(Zyphra) 기반 로컬 TTS 엔진.
    모델은 싱글톤으로 유지한다.
    """

    _instance: ZonosTTSEngine | None = None
    _model = None
    _device = None

    def __new__(cls) -> ZonosTTSEngine:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._model is not None:
            return

        self._device = available_device()
        logger.info(
            '[tts] Zonos loading model=%s, device=%s', ZONOS_MODEL, self._device
        )

        # GEMINI.md 지침에 따라 bfloat16 사용 (MPS/CUDA 공통)
        try:
            self._model = Zonos.from_pretrained(ZONOS_MODEL, device=self._device)
            if self._device != 'cpu':
                self._model = self._model.to(torch.bfloat16)
        except Exception as exc:
            logger.error('[tts] Zonos model load failed: %s', exc)
            raise TTSGenerationError(f'Zonos 모델 로드 실패: {exc}') from exc

    def _should_disable_torch_compile(self) -> bool:
        """운영체제와 컴파일러 가용성에 따라 torch.compile 사용 여부를 결정한다."""
        if self._device != 'cuda':
            return True
        if sys.platform == 'win32':
            return shutil.which('cl') is None
        return False

    def _detect_language(self, text: str, language: str | None) -> str:
        """입력 텍스트 기준으로 기본 언어 코드를 결정한다."""
        if language:
            return language
        if re.search(r'[가-힣]', text):
            return 'ko'
        return 'en-us'

    def _estimate_max_new_tokens(self, text: str, language: str) -> int:
        """텍스트 길이에 맞는 합성 상한 토큰 수를 계산한다."""
        compact_text = re.sub(r'\s+', '', text)
        if language == 'ko':
            estimated_seconds = (len(compact_text) / 6.0) + 1.5
        else:
            estimated_seconds = (len(text.split()) * 0.6) + 1.5

        estimated_seconds = min(max(estimated_seconds, 3.0), 12.0)
        return max(258, math.ceil(estimated_seconds * 86))

    def _build_output_path(self, voice_preset: str) -> Path:
        """화자명과 날짜시간 기반의 출력 파일 경로를 생성한다."""
        return self._build_output_path_with_suffix(voice_preset)

    def _build_output_path_with_suffix(
        self,
        voice_preset: str,
        suffix: str = '',
        timestamp: str | None = None,
    ) -> Path:
        """화자명과 날짜시간, 추가 suffix 기반의 출력 파일 경로를 생성한다."""
        voice_name = Path(voice_preset).stem if voice_preset else 'default'
        voice_name = re.sub(r'[^A-Za-z0-9_-]+', '_', voice_name).strip('_')
        if not voice_name:
            voice_name = 'default'

        timestamp = timestamp or datetime.now().strftime('%Y%m%d_%H%M%S')
        suffix_part = f'_{suffix}' if suffix else ''
        return TMP_DIR / f'{voice_name}_{timestamp}{suffix_part}.wav'

    def _split_text(self, text: str, language: str) -> list[str]:
        """긴 텍스트를 문장부호 우선으로 안정적으로 분할한다."""
        compact_text = re.sub(r'\s+', ' ', text).strip()
        if not compact_text:
            return []

        soft_limit = 80 if language == 'ko' else 160
        hard_limit = 120 if language == 'ko' else 220
        clause_parts = re.findall(r'[^,;:.!?。！？]+[,;:.!?。！？]?', compact_text)
        clause_parts = [part.strip() for part in clause_parts if part.strip()]
        if not clause_parts:
            clause_parts = [compact_text]

        chunks: list[str] = []
        current = ''
        for part in clause_parts:
            candidate = f'{current} {part}'.strip() if current else part
            if len(candidate) <= soft_limit:
                current = candidate
                continue

            if current:
                chunks.append(current)
                current = ''

            if len(part) <= hard_limit:
                current = part
                continue

            words = part.split()
            buffer = ''
            for word in words:
                candidate = f'{buffer} {word}'.strip() if buffer else word
                if len(candidate) <= soft_limit:
                    buffer = candidate
                    continue
                if buffer:
                    chunks.append(buffer)
                buffer = word
            if buffer:
                current = buffer

        if current:
            chunks.append(current)

        return chunks or [compact_text]

    def _build_synthesis_params(
        self,
        text: str,
        speaker: torch.Tensor,
        language: str,
        kwargs: dict,
    ) -> tuple[dict, int]:
        """청크별 Zonos 합성 파라미터를 구성한다."""
        params = {
            'text': text,
            'speaker': speaker,
            'language': language,
            'speaking_rate': kwargs.get('speaking_rate', 15.0),
            'pitch_std': kwargs.get('pitch_std', 20.0),
            'emotion': kwargs.get(
                'emotion',
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            ),
        }
        max_new_tokens = kwargs.get(
            'max_new_tokens',
            self._estimate_max_new_tokens(text, language),
        )
        return params, max_new_tokens

    def _move_to_device(self, obj):
        """중첩된 텐서 구조를 현재 디바이스로 이동한다."""
        if isinstance(obj, torch.Tensor):
            return obj.to(device=self._device)
        if isinstance(obj, list):
            return [self._move_to_device(x) for x in obj]
        if isinstance(obj, dict):
            return {k: self._move_to_device(v) for k, v in obj.items()}
        return obj

    def _synthesize_chunk(
        self,
        text: str,
        speaker: torch.Tensor,
        language: str,
        kwargs: dict,
        audio_prefix_codes: torch.Tensor | None = None,
    ) -> tuple[np.ndarray, torch.Tensor]:
        """단일 청크를 합성해 오디오와 생성 코드를 반환한다."""
        from zonos.conditioning import make_cond_dict

        params, max_new_tokens = self._build_synthesis_params(
            text, speaker, language, kwargs
        )
        cond_dict = make_cond_dict(**params)
        cond_dict = self._move_to_device(cond_dict)
        conditioning = self._model.prepare_conditioning(cond_dict)
        conditioning = self._move_to_device(conditioning)

        codes = self._model.generate(
            conditioning,
            audio_prefix_codes=audio_prefix_codes,
            max_new_tokens=max_new_tokens,
            disable_torch_compile=self._should_disable_torch_compile(),
        )

        wavs = self._model.autoencoder.decode(codes).cpu()
        audio = wavs[0].squeeze().numpy()

        if audio_prefix_codes is not None:
            prefix_wavs = self._model.autoencoder.decode(audio_prefix_codes).cpu()
            prefix_audio = prefix_wavs[0].squeeze().numpy()
            trim_samples = min(len(prefix_audio), len(audio))
            audio = audio[trim_samples:]

        return audio, codes

    def _select_prefix_codes(
        self,
        codes: torch.Tensor,
        prefix_code_count: int,
    ) -> torch.Tensor | None:
        """다음 청크 연속성을 위한 tail prefix 코드를 선택한다."""
        if prefix_code_count <= 0 or codes.shape[-1] <= 0:
            return None
        prefix_code_count = min(prefix_code_count, codes.shape[-1])
        return codes[..., -prefix_code_count:].contiguous()

    def _pause_ms_for_chunk(self, chunk: str) -> int:
        """청크 마지막 문장부호에 따라 자연스러운 pause 길이를 계산한다."""
        stripped = chunk.rstrip()
        if not stripped:
            return 0
        if stripped[-1] in '.!?。！？':
            return 180
        if stripped[-1] in ',;:':
            return 110
        return 40

    def _merge_chunks_with_pauses(
        self,
        audio_parts: list[np.ndarray],
        chunks: list[str],
        sample_rate: int = 44100,
    ) -> np.ndarray:
        """청크 오디오를 문장부호 기반 짧은 pause로 자연스럽게 이어붙인다."""
        if not audio_parts:
            return np.array([], dtype=np.float32)

        merged = audio_parts[0].astype(np.float32, copy=False)
        for index, next_audio in enumerate(audio_parts[1:], start=1):
            pause_ms = self._pause_ms_for_chunk(chunks[index - 1])
            pause_samples = int(sample_rate * (pause_ms / 1000))
            if pause_samples > 0:
                merged = np.concatenate(
                    [merged, np.zeros(pause_samples, dtype=np.float32)]
                )
            merged = np.concatenate([merged, next_audio.astype(np.float32, copy=False)])
        return merged

    def synthesize_stream(
        self,
        text: str,
        voice_preset: str = 'default',
        **kwargs,
    ) -> Iterator[TTSResult]:
        """긴 텍스트를 청크 단위로 순차 합성해 결과를 스트리밍한다."""
        if not text.strip():
            raise TTSGenerationError('TTS 입력 텍스트가 비어 있습니다.')

        dtype = torch.bfloat16 if self._device != 'cpu' else torch.float32
        language = self._detect_language(text, kwargs.get('language'))
        chunks = self._split_text(text, language)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        prefix_code_count = int(kwargs.get('prefix_code_count', 24))

        try:
            speaker = self._get_speaker_embedding(voice_preset)
            speaker = speaker.to(device=self._device, dtype=dtype)
            prefix_codes = None

            for index, chunk in enumerate(chunks, start=1):
                chunk_audio, chunk_codes = self._synthesize_chunk(
                    chunk,
                    speaker,
                    language,
                    kwargs,
                    audio_prefix_codes=prefix_codes,
                )
                prefix_codes = self._select_prefix_codes(
                    chunk_codes,
                    prefix_code_count=prefix_code_count,
                )
                chunk_path = self._build_output_path_with_suffix(
                    voice_preset,
                    suffix=f'chunk{index:02d}',
                    timestamp=timestamp,
                )
                sf.write(str(chunk_path), chunk_audio.astype(np.float32, copy=False), 44100)
                yield TTSResult(
                    audio_path=str(chunk_path),
                    voice_preset=voice_preset,
                    engine='zonos',
                    duration_sec=round(len(chunk_audio) / 44100, 2),
                )
        except Exception as exc:
            raise TTSGenerationError(f'Zonos 스트리밍 합성 실패: {exc}') from exc

    def _get_speaker_embedding(self, voice_name: str) -> torch.Tensor:
        """
        화자 이름에 따라 임베딩 가중치를 가져오거나 생성한다.
        1. data/models/voices/{voice_name}.pt 가 있으면 로드.
        2. data/voices/{voice_name}.wav 가 있으면 임베딩 생성 후 .pt로 저장.
        """

        dtype = torch.bfloat16 if self._device != 'cpu' else torch.float32

        # 1. 가중치 파일(.pt) 검색 - data/models/voices/
        weight_path = EMBEDDINGS_DIR / f'{voice_name}.pt'
        if weight_path.exists():
            return torch.load(
                weight_path, map_location=self._device, weights_only=True
            ).to(dtype=dtype)

        # 2. 직접 경로 처리 (.pt)
        preset_path = Path(voice_name)
        if preset_path.exists() and preset_path.suffix == '.pt':
            return torch.load(
                preset_path, map_location=self._device, weights_only=True
            ).to(dtype=dtype)

        # 3. 원본 오디오 파일 검색 및 임베딩 생성 - data/voices/
        audio_paths = []
        if preset_path.exists() and preset_path.suffix in [
            '.wav',
            '.mp3',
            '.m4a',
            '.flac',
        ]:
            audio_paths.append(preset_path)

        for ext in ['.wav', '.mp3', '.m4a', '.flac']:
            p = VOICES_DIR / f'{voice_name}{ext}'
            if p.exists():
                audio_paths.append(p)

        if audio_paths:
            target_audio = audio_paths[0]
            data, samplerate = sf.read(str(target_audio))
            data = data[None, :] if data.ndim == 1 else data.T
            wav = torch.from_numpy(data).float()

            speaker = self._model.make_speaker_embedding(wav, samplerate)

            # 가중치 파일은 data/models/voices/ 에 저장
            new_weight_path = EMBEDDINGS_DIR / f'{target_audio.stem}.pt'
            torch.save(speaker.cpu(), new_weight_path)
            logger.info(
                '[tts:zonos] Created and saved speaker embedding to %s', new_weight_path
            )
            return speaker.to(device=self._device, dtype=dtype)

        # 기본 화자(더미)
        logger.warning(
            '[tts:zonos] Speaker "%s" not found. Using dummy speaker.', voice_name
        )
        return torch.zeros((1, 1, 128), device=self._device, dtype=dtype)

    def synthesize(
        self, text: str, voice_preset: str = 'default', **kwargs
    ) -> TTSResult:
        """
        텍스트를 Zonos로 음성 합성한다.
        """
        if not text.strip():
            raise TTSGenerationError('TTS 입력 텍스트가 비어 있습니다.')

        out_path = self._build_output_path(voice_preset)
        dtype = torch.bfloat16 if self._device != 'cpu' else torch.float32

        try:
            t0 = time.perf_counter()

            # 화자 임베딩 가져오기
            speaker = self._get_speaker_embedding(voice_preset)
            speaker = speaker.to(device=self._device, dtype=dtype)

            language = self._detect_language(text, kwargs.get('language'))
            chunks = self._split_text(text, language)
            prefix_code_count = int(kwargs.get('prefix_code_count', 24))
            prefix_codes = None
            audio_parts: list[np.ndarray] = []
            for chunk in chunks:
                chunk_audio, chunk_codes = self._synthesize_chunk(
                    chunk,
                    speaker,
                    language,
                    kwargs,
                    audio_prefix_codes=prefix_codes,
                )
                prefix_codes = self._select_prefix_codes(
                    chunk_codes,
                    prefix_code_count=prefix_code_count,
                )
                audio_parts.append(chunk_audio.astype(np.float32, copy=False))

            audio_data = self._merge_chunks_with_pauses(
                audio_parts,
                chunks,
                sample_rate=44100,
            )
            sf.write(str(out_path), audio_data, 44100)

            inference_duration = time.perf_counter() - t0
            audio_duration = len(audio_data) / 44100
        except Exception as exc:
            raise TTSGenerationError(f'Zonos 합성 실패: {exc}') from exc

        logger.info(
            '[tts:zonos] voice=%s params=%s elapsed=%.2fs audio=%.2fs',
            voice_preset,
            kwargs,
            inference_duration,
            audio_duration,
        )
        return TTSResult(
            audio_path=str(out_path),
            voice_preset=voice_preset,
            engine='zonos',
            duration_sec=round(audio_duration, 2),
        )

    def list_presets(self) -> list[str]:
        """등록된 가중치 파일(.pt) 및 원본 음성 파일 목록을 반환."""
        presets = set()
        # 가중치 파일 목록
        if EMBEDDINGS_DIR.exists():
            for f in EMBEDDINGS_DIR.iterdir():
                if f.suffix == '.pt':
                    presets.add(f.stem)

        # 원본 음성 파일 목록
        if VOICES_DIR.exists():
            for f in VOICES_DIR.iterdir():
                if f.suffix in ['.wav', '.mp3', '.flac']:
                    presets.add(f.stem)
        return sorted(list(presets))
