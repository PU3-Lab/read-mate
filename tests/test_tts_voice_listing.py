from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from services.tts_edge import EdgeTTSEngine  # noqa: E402
from services.tts_elevenlabs import ElevenLabsTTS  # noqa: E402


class EdgeTTSEngineVoiceTests(unittest.TestCase):
    def tearDown(self) -> None:
        EdgeTTSEngine._voices_cache = None

    def test_list_presets_loads_all_korean_neural_voices(self) -> None:
        mocked_voices = [
            {'ShortName': 'ko-KR-SunHiNeural', 'Locale': 'ko-KR'},
            {'ShortName': 'ko-KR-InJoonNeural', 'Locale': 'ko-KR'},
            {'ShortName': 'en-US-AvaNeural', 'Locale': 'en-US'},
            {'ShortName': 'ko-KR-OldVoice', 'Locale': 'ko-KR'},
        ]

        with patch('edge_tts.list_voices', new=AsyncMock(return_value=mocked_voices)):
            presets = EdgeTTSEngine().list_presets()

        self.assertEqual(presets, ['ko-KR-InJoonNeural', 'ko-KR-SunHiNeural'])


class ElevenLabsTTSVoiceTests(unittest.TestCase):
    def test_list_presets_loads_all_account_voices(self) -> None:
        engine = ElevenLabsTTS(api_key='test-key')
        mocked_response = Mock()
        mocked_response.json.return_value = {
            'voices': [
                {'voice_id': 'id-2', 'name': 'Bella'},
                {'voice_id': 'id-1', 'name': 'Antoni'},
            ]
        }
        mocked_response.raise_for_status.return_value = None

        with patch('services.tts_elevenlabs.requests.get', return_value=mocked_response):
            presets = engine.list_presets()

        self.assertEqual(presets, ['Antoni', 'Bella'])

    def test_resolve_voice_accepts_voice_id(self) -> None:
        engine = ElevenLabsTTS(api_key='test-key')
        voice_map = {'Bella': 'id-2', 'Antoni': 'id-1'}

        voice_name, voice_id = engine._resolve_voice('id-1', voice_map)

        self.assertEqual(voice_name, 'Antoni')
        self.assertEqual(voice_id, 'id-1')


if __name__ == '__main__':
    unittest.main()
