"""
Zonos 로컬 TTS 엔진.

공식 예제를 기준으로 Zonos를 Hugging Face 모델에서 로드한다.
고정 화자 프리셋은 없고, 필요하면 voice_preset에 참조 오디오 경로, 저장된
화자 임베딩(.pt) 경로, 또는 저장된 보이스 이름을 넣어 화자 클로닝으로 사용한다.
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
import re
import shutil
import sys
import time
import uuid
from pathlib import Path

from core.config import (
    TMP_DIR,
    ZONOS_CFG_SCALE,
    ZONOS_DNSMOS_OVRL,
    ZONOS_EMBEDDINGS_DIR,
    ZONOS_LANGUAGE,
    ZONOS_MAX_NEW_TOKENS,
    ZONOS_MIN_P,
    ZONOS_MODEL,
    ZONOS_PITCH_STD,
    ZONOS_SPEAKING_RATE,
)
from core.exceptions import TTSGenerationError
from lib.utils.device import available_device
from models.schemas import TTSResult
from services.base import BaseTTS

logger = logging.getLogger(__name__)

_DEFAULT_PRESET = 'default'


class ZonosEngine(BaseTTS):
    """
    Zyphra Zonos 기반 로컬 TTS 엔진.

    주의:
    - 공식 구현은 고정 화자 목록보다 speaker embedding/voice cloning에 초점이 있다.
    - voice_preset이 파일 경로이거나 저장된 보이스 이름이면 참조 오디오(.wav)
      또는 화자 임베딩(.pt)으로 간주해 화자 클로닝을 시도한다.
    - eSpeak-ng 시스템 의존성이 필요하다.
    """

    _instance: ZonosEngine | None = None
    _model = None

    def __new__(cls) -> ZonosEngine:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        model_name: str = ZONOS_MODEL,
        language: str = ZONOS_LANGUAGE,
        max_new_tokens: int = ZONOS_MAX_NEW_TOKENS,
        cfg_scale: float = ZONOS_CFG_SCALE,
        min_p: float = ZONOS_MIN_P,
        speaking_rate: float = ZONOS_SPEAKING_RATE,
        pitch_std: float = ZONOS_PITCH_STD,
        dnsmos_ovrl: float = ZONOS_DNSMOS_OVRL,
    ) -> None:
        if self._model is not None:
            return

        self.model_name = model_name
        self.language = language
        self.max_new_tokens = max_new_tokens
        self.cfg_scale = cfg_scale
        self.min_p = min_p
        self.speaking_rate = speaking_rate
        self.pitch_std = pitch_std
        self.dnsmos_ovrl = dnsmos_ovrl
        self.embeddings_dir = ZONOS_EMBEDDINGS_DIR
        self.device = self._resolve_device()
        self._validate_runtime()

        try:
            from zonos.model import Zonos
        except Exception as exc:
            raise TTSGenerationError(
                self._build_runtime_error_message(
                    'Zonos import 실패',
                    extra='`zonos.model`을 불러오지 못했습니다.',
                )
            ) from exc

        logger.info('[tts] Zonos loading model=%s device=%s', model_name, self.device)
        try:
            self._zonos = Zonos.from_pretrained(model_name, device=self.device)
            self._maybe_enable_bfloat16()
            self._model = True
        except Exception as exc:
            raise TTSGenerationError(f'Zonos 로딩 실패: {exc}') from exc

        logger.info('[tts] Zonos loading complete model=%s', model_name)

    def synthesize(self, text: str, voice_preset: str = _DEFAULT_PRESET) -> TTSResult:
        """
        텍스트를 Zonos로 음성 합성한다.

        voice_preset이 실제 파일 경로나 저장된 보이스 이름이면 참조 화자
        오디오(.wav) 또는 speaker embedding(.pt)으로 사용한다.
        그렇지 않으면 speaker를 비조건부로 두고 기본 화자로 생성한다.
        """
        if not text.strip():
            raise TTSGenerationError('TTS 입력 텍스트가 비어 있습니다.')

        try:
            import torch
            import torchaudio
            from zonos.conditioning import make_cond_dict
        except Exception as exc:
            raise TTSGenerationError(
                'Zonos 추론 의존성 import 실패: torch/torchaudio/zonos 설치를 확인하세요.'
            ) from exc

        speaker_source_path = self._resolve_speaker_source(voice_preset)
        speaker = None
        used_preset = _DEFAULT_PRESET

        try:
            if speaker_source_path is not None:
                speaker = self._load_or_make_speaker_embedding(
                    speaker_source_path=speaker_source_path,
                    torch=torch,
                    torchaudio=torchaudio,
                )
                used_preset = str(speaker_source_path)

            t0 = time.perf_counter()
            cond_dict = self._make_conditioning_dict(
                make_cond_dict=make_cond_dict,
                text=text,
                speaker=speaker,
            )
            conditioning = self._zonos.prepare_conditioning(cond_dict)
            generate_kwargs = self._build_generate_kwargs()
            with torch.inference_mode():
                codes = self._zonos.generate(
                    conditioning,
                    **generate_kwargs,
                )
            wavs = self._zonos.autoencoder.decode(codes).cpu()
            waveform = self._normalize_waveform(wavs)
            out_path = TMP_DIR / f'{uuid.uuid4().hex}.wav'
            self._save_waveform(
                out_path=out_path,
                waveform=waveform,
                sampling_rate=self._zonos.autoencoder.sampling_rate,
                torchaudio=torchaudio,
            )
            duration = time.perf_counter() - t0
        except Exception as exc:
            raise TTSGenerationError(f'Zonos 합성 실패: {exc}') from exc

        logger.info(
            '[tts:zonos] voice=%s language=%s chars=%d elapsed=%.2fs '
            'cfg_scale=%.2f min_p=%.2f speaking_rate=%.1f pitch_std=%.1f',
            used_preset,
            self.language,
            len(text),
            duration,
            self.cfg_scale,
            self.min_p,
            self.speaking_rate,
            self.pitch_std,
        )
        return TTSResult(
            audio_path=str(out_path),
            voice_preset=used_preset,
            engine=f'zonos/{self.model_name}',
            duration_sec=round(duration, 2),
        )

    def list_presets(self) -> list[str]:
        """
        Zonos는 저장된 보이스 라이브러리를 프리셋처럼 노출한다.
        """
        saved_voices = sorted(path.stem for path in self.embeddings_dir.glob('*.pt'))
        return [_DEFAULT_PRESET, *saved_voices]

    def save_voice(self, source_path: str, voice_name: str) -> str:
        """참조 오디오를 이름 있는 보이스로 저장한다."""
        normalized_name = self._normalize_voice_name(voice_name)
        embedding_path = self.embeddings_dir / f'{normalized_name}.pt'
        return self.save_speaker_embedding(source_path, str(embedding_path))

    def _make_conditioning_dict(self, make_cond_dict, text: str, speaker):
        """
        speaker가 없으면 비조건부 speaker로 생성한다.
        이 동작은 공식 gradio/issue 예제의 unconditional_keys 사용을 따른다.
        """
        kwargs = {
            'text': text,
            'language': self.language,
            'speaking_rate': self.speaking_rate,
            'pitch_std': self.pitch_std,
            'dnsmos_ovrl': self.dnsmos_ovrl,
        }
        if speaker is not None:
            kwargs['speaker'] = speaker
        else:
            kwargs['speaker'] = None
            kwargs['unconditional_keys'] = ['speaker']

        return make_cond_dict(**self._filter_supported_kwargs(make_cond_dict, kwargs))

    def _build_generate_kwargs(self) -> dict:
        """현재 설치된 Zonos generate 시그니처에 맞는 생성 인자만 전달한다."""
        kwargs = {
            'max_new_tokens': self.max_new_tokens,
            'cfg_scale': self.cfg_scale,
            'sampling_params': {'min_p': self.min_p},
        }
        return self._filter_supported_kwargs(self._zonos.generate, kwargs)

    @staticmethod
    def _filter_supported_kwargs(func, kwargs: dict) -> dict:
        """지원하는 키워드 인자만 남겨 버전별 API 차이를 흡수한다."""
        signature = inspect.signature(func)
        supported = set(signature.parameters)
        return {key: value for key, value in kwargs.items() if key in supported}

    def _make_speaker_embedding(self, wav, sampling_rate):
        """현재 설치된 Zonos 버전에 맞는 speaker embedding API를 선택한다."""
        if hasattr(self._zonos, 'make_speaker_embedding'):
            return self._zonos.make_speaker_embedding(wav, sampling_rate)
        if hasattr(self._zonos, 'embed_spk_audio'):
            return self._zonos.embed_spk_audio(wav, sampling_rate)
        raise TTSGenerationError('Zonos speaker embedding API를 찾지 못했습니다.')

    def _load_or_make_speaker_embedding(
        self, speaker_source_path: Path, torch, torchaudio
    ):
        """참조 오디오 또는 저장된 .pt speaker embedding을 speaker 조건으로 변환한다."""
        if speaker_source_path.suffix.lower() == '.pt':
            return self._load_speaker_embedding(speaker_source_path, torch=torch)

        wav, sampling_rate = self._load_speaker_audio(
            speaker_source_path,
            torch=torch,
            torchaudio=torchaudio,
        )
        return self._make_speaker_embedding(wav, sampling_rate)

    def save_speaker_embedding(
        self,
        speaker_audio_path: str,
        embedding_path: str,
    ) -> str:
        """
        참조 오디오에서 speaker embedding을 추출해 .pt 파일로 저장한다.
        """
        try:
            import torch
            import torchaudio
        except Exception as exc:
            raise TTSGenerationError(
                'Zonos 임베딩 저장 의존성 import 실패: torch/torchaudio 설치를 확인하세요.'
            ) from exc

        source_path = self._resolve_speaker_source(speaker_audio_path)
        if source_path is None or source_path.suffix.lower() == '.pt':
            raise TTSGenerationError(
                'speaker embedding 저장에는 참조 오디오 파일이 필요합니다.'
            )

        wav, sampling_rate = self._load_speaker_audio(
            source_path,
            torch=torch,
            torchaudio=torchaudio,
        )
        speaker = self._make_speaker_embedding(wav, sampling_rate)

        out_path = Path(embedding_path).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(speaker, str(out_path))
        return str(out_path)

    @staticmethod
    def _load_speaker_audio(speaker_audio_path: Path, torch, torchaudio):
        """
        참조 오디오는 soundfile 우선 로드한다.

        macOS/CPU 조합에서 일부 torchaudio backend가 TorchCodec을 요구해
        실패하는 경우가 있어, 일반 WAV 입력은 soundfile로 먼저 처리한다.
        """
        try:
            import soundfile as sf

            audio, sampling_rate = sf.read(
                str(speaker_audio_path),
                dtype='float32',
                always_2d=True,
            )
            return torch.from_numpy(audio.T), sampling_rate
        except Exception:
            return torchaudio.load(str(speaker_audio_path))

    def _load_speaker_embedding(self, speaker_embedding_path: Path, torch):
        """저장된 .pt speaker embedding을 현재 디바이스에 맞게 로드한다."""
        speaker = torch.load(str(speaker_embedding_path), map_location=self.device)
        if hasattr(speaker, 'to'):
            return speaker.to(self.device)
        return speaker

    @staticmethod
    def _normalize_waveform(wavs):
        """
        저장 전 [channels, samples] 텐서로 정규화한다.
        """
        if wavs.ndim == 3:
            wavs = wavs[0]
        if wavs.ndim == 1:
            wavs = wavs.unsqueeze(0)
        if wavs.ndim != 2:
            raise TTSGenerationError(
                f'예상하지 못한 Zonos waveform shape: {tuple(wavs.shape)}'
            )
        return wavs

    @staticmethod
    def _save_waveform(
        out_path: Path, waveform, sampling_rate: int, torchaudio
    ) -> None:
        """
        생성 결과는 soundfile 우선 저장한다.

        현재 macOS/CPU 조합의 torchaudio.save는 TorchCodec을 요구할 수 있어,
        일반 torch.Tensor면 soundfile로 먼저 저장하고 실패 시 torchaudio로 폴백한다.
        """
        if all(
            hasattr(waveform, attr) for attr in ('detach', 'cpu', 'transpose', 'numpy')
        ):
            try:
                import numpy as np
                import soundfile as sf

                audio = waveform.detach().cpu().transpose(0, 1).numpy()
                audio = ZonosEngine._trim_leading_silence(
                    audio=audio,
                    sampling_rate=sampling_rate,
                    np=np,
                )
                sf.write(str(out_path), audio, sampling_rate)
                return
            except Exception:
                pass

        torchaudio.save(str(out_path), waveform, sampling_rate)

    @staticmethod
    def _trim_leading_silence(audio, sampling_rate: int, np):
        """
        선행 무음을 제거하되, 시작 직후 짧은 아티팩트 후 긴 무음이 오면
        다음 실제 발화 시작점으로 넘긴다.
        """
        if audio.ndim == 1:
            mono = np.abs(audio)
        else:
            mono = np.mean(np.abs(audio), axis=1)

        frame_size = max(1, int(sampling_rate * 0.02))
        lookback_frames = 1
        min_active_frames = 8
        long_silence_frames = 25
        rms_threshold = 0.01

        frame_starts = list(range(0, max(1, len(mono) - frame_size + 1), frame_size))
        rms_frames = np.array(
            [
                np.sqrt(np.mean(mono[start : start + frame_size] ** 2))
                for start in frame_starts
            ],
            dtype='float32',
        )
        active = rms_frames >= rms_threshold

        runs: list[tuple[int, int]] = []
        idx = 0
        while idx < len(active):
            if not active[idx]:
                idx += 1
                continue
            start = idx
            while idx < len(active) and active[idx]:
                idx += 1
            end = idx
            if end - start >= min_active_frames:
                runs.append((start, end))

        if not runs:
            return audio

        target_start = runs[0][0]
        if len(runs) >= 2:
            first_end = runs[0][1]
            next_start = runs[1][0]
            if (
                runs[0][0] <= lookback_frames
                and next_start - first_end >= long_silence_frames
            ):
                target_start = next_start

        sample_start = max(0, (target_start - lookback_frames) * frame_size)
        if sample_start == 0:
            return audio

        trimmed = audio[sample_start:]
        logger.info(
            '[tts:zonos] trimmed leading silence %.2fs -> %.2fs',
            sample_start / sampling_rate,
            len(trimmed) / sampling_rate,
        )
        return trimmed

    @staticmethod
    def _resolve_speaker_source(voice_preset: str) -> Path | None:
        """voice_preset이 실제 파일 경로나 저장된 이름이면 speaker source로 사용한다."""
        if not voice_preset or voice_preset == _DEFAULT_PRESET:
            return None

        path = Path(voice_preset).expanduser()
        if not path.is_file():
            normalized_name = ZonosEngine._normalize_voice_name(voice_preset)
            library_path = ZONOS_EMBEDDINGS_DIR / f'{normalized_name}.pt'
            if library_path.is_file():
                return library_path
            raise TTSGenerationError(
                f'Zonos 화자 클로닝용 speaker source를 찾을 수 없습니다: {voice_preset}'
            )
        return path

    @staticmethod
    def _normalize_voice_name(voice_name: str) -> str:
        """보이스 이름을 파일명으로 안전하게 정규화한다."""
        normalized = re.sub(r'[^A-Za-z0-9._-]+', '_', voice_name.strip())
        normalized = normalized.strip('._')
        if not normalized:
            raise TTSGenerationError('보이스 이름이 비어 있습니다.')
        return normalized

    @staticmethod
    def _resolve_device() -> str:
        """
        Zonos는 공식 문서 기준 CUDA/CPU 중심이므로, MPS는 우선 CPU로 내린다.
        """
        device = available_device()
        if device == 'mps':
            logger.info('[tts:zonos] MPS는 검증되지 않아 cpu로 폴백')
            return 'cpu'
        return device

    def _validate_runtime(self) -> None:
        """
        Zonos 런타임에 필요한 시스템/파이썬 의존성이 준비됐는지 확인한다.

        범용성을 위해 설치를 자동 수행하지 않고, 현재 OS에 맞는 안내 메시지를 제공한다.
        """
        if not self._has_espeak():
            raise TTSGenerationError(
                self._build_runtime_error_message(
                    'Zonos 런타임 준비 실패',
                    extra='eSpeak 실행 파일을 찾지 못했습니다.',
                )
            )

        if self._find_spec_safe('zonos') is None:
            raise TTSGenerationError(
                self._build_runtime_error_message(
                    'Zonos 런타임 준비 실패',
                    extra='`zonos` 파이썬 패키지를 찾지 못했습니다.',
                )
            )

        if self._find_spec_safe('zonos.model') is None:
            raise TTSGenerationError(
                self._build_runtime_error_message(
                    'Zonos 런타임 준비 실패',
                    extra='`zonos.model` 모듈을 찾지 못했습니다. '
                    'PyPI wheel 대신 공식 소스를 editable install 해야 할 수 있습니다.',
                )
            )

        if self._find_spec_safe('zonos.backbone') is None:
            raise TTSGenerationError(
                self._build_runtime_error_message(
                    'Zonos 런타임 준비 실패',
                    extra='`zonos.backbone` 모듈이 없습니다. '
                    '공식 소스 설치가 완전하지 않습니다.',
                )
            )

    @staticmethod
    def _has_espeak() -> bool:
        """eSpeak 또는 eSpeak NG 실행 파일 존재 여부 확인."""
        return (
            shutil.which('espeak-ng') is not None or shutil.which('espeak') is not None
        )

    @staticmethod
    def _find_spec_safe(module_name: str):
        """일부 namespace/mock 모듈에서 find_spec가 ValueError를 낼 수 있어 이를 흡수한다."""
        try:
            return importlib.util.find_spec(module_name)
        except ValueError:
            if module_name in sys.modules:
                return object()
            return None

    @classmethod
    def _build_runtime_error_message(cls, title: str, extra: str = '') -> str:
        """현재 OS에 맞는 Zonos 설치 가이드를 포함한 에러 메시지 생성."""
        parts = [title]
        if extra:
            parts.append(extra)
        parts.append('필요 조건: eSpeak 시스템 라이브러리 + 공식 Zonos 소스 설치.')
        parts.append(cls._platform_install_hint())
        parts.append(cls._python_install_hint())
        return ' '.join(parts)

    @staticmethod
    def _platform_install_hint() -> str:
        """OS별 eSpeak 설치 가이드."""
        if sys.platform == 'darwin':
            return 'macOS: `brew install espeak-ng`.'
        if sys.platform.startswith('linux'):
            return (
                'Linux: 배포판 패키지 매니저로 `espeak-ng` 설치 '
                '(예: Debian/Ubuntu `apt install -y espeak-ng`).'
            )
        if sys.platform == 'win32':
            return (
                'Windows: eSpeak NG를 수동 설치하고 필요하면 '
                '`PHONEMIZER_ESPEAK_LIBRARY`를 설정하세요. '
                'Zonos의 Windows 지원은 실험적입니다.'
            )
        return '현재 OS에 맞는 `espeak-ng` 설치가 필요합니다.'

    @staticmethod
    def _python_install_hint() -> str:
        """공식 README 기준 Zonos 파이썬 설치 가이드."""
        return (
            'Python 환경: 공식 Zonos 저장소를 clone한 뒤 '
            '`uv pip install -e /path/to/Zonos` 또는 저장소 내부에서 '
            '`uv pip install -e .`를 실행하세요.'
        )

    def _maybe_enable_bfloat16(self) -> None:
        """CUDA 환경에서 bfloat16 사용이 가능하면 모델 dtype을 낮춘다."""
        if self.device != 'cuda':
            return

        try:
            self._zonos.bfloat16()
        except Exception:
            logger.info('[tts:zonos] bfloat16 전환 생략')
