"""
ReadMate Zonos TTS 서비스 구현체.
Zyphra의 Zonos 모델을 사용하여 고성능 TTS와 세밀한 음성 조절을 제공한다.
"""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

import torch

from core.config import EMBEDDINGS_DIR, TMP_DIR, VOICES_DIR, ZONOS_MODEL
from core.exceptions import TTSGenerationError
from lib.utils.device import available_device
from models.schemas import TTSResult
from services.base import BaseTTS

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

        from zonos.model import Zonos

        self._device = available_device()
        logger.info('[tts] Zonos loading model=%s, device=%s', ZONOS_MODEL, self._device)

        # GEMINI.md 지침에 따라 bfloat16 사용 (MPS/CUDA 공통)
        try:
            self._model = Zonos.from_pretrained(ZONOS_MODEL, device=self._device)
            if self._device != 'cpu':
                self._model = self._model.to(torch.bfloat16)
        except Exception as exc:
            logger.error('[tts] Zonos model load failed: %s', exc)
            raise TTSGenerationError(f'Zonos 모델 로드 실패: {exc}') from exc

    def _get_speaker_embedding(self, voice_name: str) -> torch.Tensor:
        """
        화자 이름에 따라 임베딩 가중치를 가져오거나 생성한다.
        1. data/models/voices/{voice_name}.pt 가 있으면 로드.
        2. data/voices/{voice_name}.wav 가 있으면 임베딩 생성 후 .pt로 저장.
        """
        import soundfile as sf

        dtype = torch.bfloat16 if self._device != 'cpu' else torch.float32

        # 1. 가중치 파일(.pt) 검색 - data/models/voices/
        weight_path = EMBEDDINGS_DIR / f'{voice_name}.pt'
        if weight_path.exists():
            return torch.load(weight_path, map_location=self._device, weights_only=True).to(dtype=dtype)

        # 2. 직접 경로 처리 (.pt)
        preset_path = Path(voice_name)
        if preset_path.exists() and preset_path.suffix == '.pt':
            return torch.load(preset_path, map_location=self._device, weights_only=True).to(dtype=dtype)

        # 3. 원본 오디오 파일 검색 및 임베딩 생성 - data/voices/
        audio_paths = []
        if preset_path.exists() and preset_path.suffix in ['.wav', '.mp3', '.m4a', '.flac']:
            audio_paths.append(preset_path)
        
        for ext in ['.wav', '.mp3', '.m4a', '.flac']:
            p = VOICES_DIR / f'{voice_name}{ext}'
            if p.exists():
                audio_paths.append(p)

        if audio_paths:
            target_audio = audio_paths[0]
            data, samplerate = sf.read(str(target_audio))
            if data.ndim == 1:
                data = data[None, :]
            else:
                data = data.T
            wav = torch.from_numpy(data).float()
            
            speaker = self._model.make_speaker_embedding(wav, samplerate)
            
            # 가중치 파일은 data/models/voices/ 에 저장
            new_weight_path = EMBEDDINGS_DIR / f'{target_audio.stem}.pt'
            torch.save(speaker.cpu(), new_weight_path)
            logger.info('[tts:zonos] Created and saved speaker embedding to %s', new_weight_path)
            return speaker.to(device=self._device, dtype=dtype)

        # 기본 화자(더미)
        logger.warning('[tts:zonos] Speaker "%s" not found. Using dummy speaker.', voice_name)
        return torch.zeros((1, 1, 128), device=self._device, dtype=dtype)

    def synthesize(self, text: str, voice_preset: str = 'default', **kwargs) -> TTSResult:
        """
        텍스트를 Zonos로 음성 합성한다.
        """
        if not text.strip():
            raise TTSGenerationError('TTS 입력 텍스트가 비어 있습니다.')

        from zonos.conditioning import make_cond_dict

        out_path = TMP_DIR / f'{uuid.uuid4().hex}.wav'
        dtype = torch.bfloat16 if self._device != 'cpu' else torch.float32

        try:
            t0 = time.perf_counter()

            # 화자 임베딩 가져오기
            speaker = self._get_speaker_embedding(voice_preset)
            speaker = speaker.to(device=self._device, dtype=dtype)

            # 기본값 설정 및 사용자 파라미터 적용
            params = {
                'text': text,
                'speaker': speaker,
                'language': kwargs.get('language', 'en-us'),
                'speaking_rate': kwargs.get('speaking_rate', 1.0),
                'pitch_std': kwargs.get('pitch_std', 1.0),
            }

            cond_dict = make_cond_dict(**params)

            def move_to_device(obj):
                if isinstance(obj, torch.Tensor):
                    return obj.to(device=self._device)
                elif isinstance(obj, list):
                    return [move_to_device(x) for x in obj]
                elif isinstance(obj, dict):
                    return {k: move_to_device(v) for k, v in obj.items()}
                return obj

            cond_dict = move_to_device(cond_dict)
            conditioning = self._model.prepare_conditioning(cond_dict)
            conditioning = move_to_device(conditioning)

            codes = self._model.generate(
                conditioning, disable_torch_compile=self._device != 'cuda'
            )

            wavs = self._model.autoencoder.decode(codes).cpu()
            import soundfile as sf
            audio_data = wavs[0].squeeze().numpy()
            sf.write(str(out_path), audio_data, 44100)

            duration = time.perf_counter() - t0
        except Exception as exc:
            raise TTSGenerationError(f'Zonos 합성 실패: {exc}') from exc

        logger.info(
            '[tts:zonos] voice=%s params=%s elapsed=%.2fs',
            voice_preset,
            kwargs,
            duration,
        )
        return TTSResult(
            audio_path=str(out_path),
            voice_preset=voice_preset,
            engine='zonos',
            duration_sec=round(duration, 2),
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
