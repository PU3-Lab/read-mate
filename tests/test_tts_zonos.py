from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

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
        fake_torchaudio_module.save = lambda path, waveform, sr: Path(path).write_bytes(b'RIFF')

        fake_torch_module = types.ModuleType('torch')

        class _InferenceMode:
            def __enter__(self):
                return None

            def __exit__(self, exc_type, exc, tb):
                return False

        fake_torch_module.inference_mode = lambda: _InferenceMode()

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
        with patch('services.tts_zonos.shutil.which', return_value='/usr/bin/espeak-ng'):
            def fake_find_spec(name: str):
                if name in {'zonos', 'zonos.model'}:
                    return object()
                return None

            with patch('services.tts_zonos.importlib.util.find_spec', side_effect=fake_find_spec):
                with patch('services.tts_zonos.available_device', return_value='cpu'):
                    with self.assertRaisesRegex(Exception, 'zonos.backbone'):
                        ZonosEngine()


if __name__ == '__main__':
    unittest.main()
