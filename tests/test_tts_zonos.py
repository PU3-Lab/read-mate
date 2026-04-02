from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from services.tts_factory import TTSFactory  # noqa: E402
from services.tts_zonos import ZonosEngine  # noqa: E402


class FakeAutoencoder:
    sampling_rate = 44100

    @staticmethod
    def decode(_codes):
        class FakeWave:
            ndim = 3
            shape = (1, 1, 4)

            def cpu(self):
                return self

            def __getitem__(self, _index):
                return FakeWave2D()

        class FakeWave2D:
            ndim = 2
            shape = (1, 4)

        return FakeWave()


class FakeZonosModel:
    def __init__(self) -> None:
        self.autoencoder = FakeAutoencoder()

    @classmethod
    def from_pretrained(cls, model_name: str, device: str):
        instance = cls()
        instance.model_name = model_name
        instance.device = device
        return instance

    def bfloat16(self):
        return None

    def make_speaker_embedding(self, wav, sampling_rate):
        return ('speaker', wav, sampling_rate)

    def prepare_conditioning(self, cond_dict):
        return cond_dict

    def generate(self, conditioning, max_new_tokens: int):
        return ('codes', conditioning, max_new_tokens)


class ZonosEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        ZonosEngine._instance = None
        ZonosEngine._model = None

    def _install_fake_modules(self):
        fake_zonos_package = types.ModuleType('zonos')
        fake_zonos_package.__path__ = []

        fake_zonos_model_module = types.ModuleType('zonos.model')
        fake_zonos_model_module.Zonos = FakeZonosModel

        fake_zonos_backbone_module = types.ModuleType('zonos.backbone')
        fake_zonos_conditioning_module = types.ModuleType('zonos.conditioning')
        fake_zonos_conditioning_module.make_cond_dict = lambda **kwargs: kwargs

        fake_torchaudio_module = types.ModuleType('torchaudio')
        fake_torchaudio_module.load = lambda path: ('wav', 16000)
        fake_torchaudio_module.save = lambda path, waveform, sr: Path(path).write_bytes(
            b'RIFF'
        )

        fake_torch_module = types.ModuleType('torch')

        class _InferenceMode:
            def __enter__(self):
                return None

            def __exit__(self, exc_type, exc, tb):
                return False

        fake_torch_module.inference_mode = lambda: _InferenceMode()
        fake_torch_module.load = lambda path, map_location=None: (
            'loaded-speaker',
            path,
            map_location,
        )
        fake_torch_module.save = lambda obj, path: Path(path).write_bytes(b'PT')

        modules = {
            'zonos': fake_zonos_package,
            'zonos.backbone': fake_zonos_backbone_module,
            'zonos.model': fake_zonos_model_module,
            'zonos.conditioning': fake_zonos_conditioning_module,
            'torchaudio': fake_torchaudio_module,
            'torch': fake_torch_module,
        }
        modules['zonos'].backbone = fake_zonos_backbone_module
        modules['zonos'].model = fake_zonos_model_module
        modules['zonos'].conditioning = fake_zonos_conditioning_module
        return patch.dict(sys.modules, modules)

    def test_factory_registers_zonos(self) -> None:
        self.assertIn('zonos', TTSFactory.available())

    def test_list_presets_returns_default_only(self) -> None:
        with self._install_fake_modules():
            with patch('services.tts_zonos.available_device', return_value='cpu'):
                engine = ZonosEngine()
                self.assertEqual(engine.list_presets(), ['default'])

    def test_synthesize_accepts_reference_audio_path(self) -> None:
        with tempfile.NamedTemporaryFile(suffix='.wav') as ref_audio:
            with self._install_fake_modules():
                with patch('services.tts_zonos.available_device', return_value='cpu'):
                    engine = ZonosEngine()
                    result = engine.synthesize('hello world', ref_audio.name)

        self.assertTrue(result.audio_path.endswith('.wav'))
        self.assertEqual(result.voice_preset, ref_audio.name)
        self.assertIn('zonos/', result.engine)

    def test_synthesize_accepts_saved_embedding_path(self) -> None:
        with tempfile.NamedTemporaryFile(suffix='.pt') as speaker_embedding:
            with self._install_fake_modules():
                with patch('services.tts_zonos.available_device', return_value='cpu'):
                    engine = ZonosEngine()
                    result = engine.synthesize('hello world', speaker_embedding.name)

        self.assertTrue(result.audio_path.endswith('.wav'))
        self.assertEqual(result.voice_preset, speaker_embedding.name)
        self.assertIn('zonos/', result.engine)

    def test_list_presets_includes_saved_voice_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            voices_dir = Path(temp_dir)
            (voices_dir / 'kim.pt').write_bytes(b'PT')
            (voices_dir / 'narrator.pt').write_bytes(b'PT')

            with self._install_fake_modules():
                with patch('services.tts_zonos.available_device', return_value='cpu'):
                    with patch('services.tts_zonos.ZONOS_EMBEDDINGS_DIR', voices_dir):
                        engine = ZonosEngine()
                        engine.embeddings_dir = voices_dir
                        self.assertEqual(
                            engine.list_presets(),
                            ['default', 'kim', 'narrator'],
                        )

    def test_resolve_speaker_source_accepts_saved_voice_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            voices_dir = Path(temp_dir)
            voice_path = voices_dir / 'kim.pt'
            voice_path.write_bytes(b'PT')

            with patch('services.tts_zonos.ZONOS_EMBEDDINGS_DIR', voices_dir):
                resolved = ZonosEngine._resolve_speaker_source('kim')

        self.assertEqual(resolved, voice_path)

    def test_runtime_error_message_is_platform_aware_on_macos(self) -> None:
        with patch('services.tts_zonos.sys.platform', 'darwin'):
            message = ZonosEngine._build_runtime_error_message(
                'Zonos 런타임 준비 실패',
                extra='테스트',
            )

        self.assertIn('brew install espeak-ng', message)
        self.assertIn('uv pip install -e /path/to/Zonos', message)

    def test_runtime_error_message_is_platform_aware_on_linux(self) -> None:
        with patch('services.tts_zonos.sys.platform', 'linux'):
            message = ZonosEngine._build_runtime_error_message(
                'Zonos 런타임 준비 실패',
            )

        self.assertIn('apt install -y espeak-ng', message)

    def test_runtime_validation_detects_missing_backbone_module(self) -> None:
        with patch(
            'services.tts_zonos.shutil.which', return_value='/usr/bin/espeak-ng'
        ):

            def fake_find_spec(name: str):
                if name in {'zonos', 'zonos.model'}:
                    return object()
                return None

            with patch(
                'services.tts_zonos.importlib.util.find_spec',
                side_effect=fake_find_spec,
            ):
                with patch('services.tts_zonos.available_device', return_value='cpu'):
                    with self.assertRaisesRegex(Exception, 'zonos.backbone'):
                        ZonosEngine()

    def test_trim_leading_silence_skips_spurious_opening_burst(self) -> None:
        sr = 100
        opening_burst = np.ones((20, 1), dtype=np.float32) * 0.2
        long_silence = np.zeros((60, 1), dtype=np.float32)
        speech = np.ones((30, 1), dtype=np.float32) * 0.2
        audio = np.concatenate([opening_burst, long_silence, speech], axis=0)

        trimmed = ZonosEngine._trim_leading_silence(audio, sr, np)

        self.assertLess(trimmed.shape[0], audio.shape[0])
        self.assertAlmostEqual(float(trimmed[0, 0]), 0.0, places=6)
        self.assertGreater(float(trimmed[-1, 0]), 0.0)

    def test_trim_leading_silence_keeps_normal_start(self) -> None:
        sr = 100
        speech = np.ones((40, 1), dtype=np.float32) * 0.2

        trimmed = ZonosEngine._trim_leading_silence(speech, sr, np)

        self.assertEqual(trimmed.shape, speech.shape)


if __name__ == '__main__':
    unittest.main()
