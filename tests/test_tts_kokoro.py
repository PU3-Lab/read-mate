from __future__ import annotations

import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from services.tts_kokoro import KokoroEngine  # noqa: E402


class KokoroEngineCompatTests(unittest.TestCase):
    def test_patch_phonemizer_compat_adds_missing_set_data_path(self) -> None:
        wrapper_cls = type('FakeEspeakWrapper', (), {'set_library': classmethod(lambda cls, _: None)})
        api_cls = type('FakeEspeakAPI', (), {})
        fake_wrapper_module = types.ModuleType('phonemizer.backend.espeak.wrapper')
        fake_wrapper_module.EspeakWrapper = wrapper_cls
        fake_api_module = types.ModuleType('phonemizer.backend.espeak.api')
        fake_api_module.EspeakAPI = api_cls

        fake_loader_module = types.ModuleType('espeakng_loader')
        fake_loader_module.get_library_path = lambda: '/opt/homebrew/lib/libespeak-ng.dylib'
        fake_loader_module.get_data_path = lambda: '/opt/homebrew/share/espeak-ng-data'

        with patch.dict(
            sys.modules,
            {
                'phonemizer.backend.espeak.wrapper': fake_wrapper_module,
                'phonemizer.backend.espeak.api': fake_api_module,
                'espeakng_loader': fake_loader_module,
            },
        ):
            with patch.dict('os.environ', {}, clear=True):
                KokoroEngine._patch_phonemizer_compat()
                wrapper_cls.set_data_path('/tmp/espeak-data')
                self.assertEqual(os.environ['PHONEMIZER_ESPEAK_DATA_PATH'], '/tmp/espeak-data')

        self.assertTrue(hasattr(wrapper_cls, 'set_data_path'))
        self.assertTrue(getattr(api_cls, '_readmate_patched_data_path', False))


if __name__ == '__main__':
    unittest.main()
