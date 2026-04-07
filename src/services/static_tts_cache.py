"""
Static TTS audio lookup for pre-generated accessibility prompts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from core.config import STATIC_TTS_DIR, STATIC_TTS_MANIFEST


@dataclass(frozen=True)
class StaticTTSAudio:
    """Resolved static audio file for a prompt."""

    audio_path: Path
    media_type: str


def normalize_tts_text(text: str) -> str:
    """Collapse whitespace so minor formatting differences still match."""
    return ' '.join(text.split())


class StaticTTSAudioCache:
    """Manifest-backed lookup for prompt -> pre-generated audio."""

    def __init__(
        self,
        manifest_path: Path = STATIC_TTS_MANIFEST,
        base_dir: Path = STATIC_TTS_DIR,
    ) -> None:
        self.manifest_path = manifest_path
        self.base_dir = base_dir

    def find_audio(self, text: str, voice_name: str | None = None) -> StaticTTSAudio | None:
        """Return a matching static audio file when one is registered."""
        normalized_text = normalize_tts_text(text)
        if not normalized_text:
            return None

        for entry in self._load_entries():
            entry_text = normalize_tts_text(str(entry.get('text') or ''))
            if entry_text != normalized_text:
                continue

            entry_voice = str(entry.get('voice_name') or '').strip()
            if entry_voice and entry_voice != '*' and voice_name and entry_voice != voice_name:
                continue
            if entry_voice and entry_voice != '*' and not voice_name:
                continue

            audio_file = str(entry.get('audio_file') or '').strip()
            if not audio_file:
                continue

            audio_path = self._resolve_audio_path(audio_file)
            if not audio_path.exists() or not audio_path.is_file():
                continue

            return StaticTTSAudio(
                audio_path=audio_path,
                media_type=self._guess_media_type(audio_path),
            )
        return None

    def _load_entries(self) -> list[dict[str, object]]:
        if not self.manifest_path.exists():
            return []

        try:
            payload = json.loads(self.manifest_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            return []

        if isinstance(payload, list):
            return [entry for entry in payload if isinstance(entry, dict)]

        if isinstance(payload, dict):
            entries = payload.get('entries', [])
            if isinstance(entries, list):
                return [entry for entry in entries if isinstance(entry, dict)]

        return []

    def _resolve_audio_path(self, audio_file: str) -> Path:
        candidate = Path(audio_file)
        if candidate.is_absolute():
            return candidate
        return self.base_dir / candidate

    @staticmethod
    def _guess_media_type(audio_path: Path) -> str:
        suffix = audio_path.suffix.lower()
        if suffix == '.mp3':
            return 'audio/mpeg'
        if suffix == '.wav':
            return 'audio/wav'
        if suffix == '.ogg':
            return 'audio/ogg'
        if suffix == '.m4a':
            return 'audio/mp4'
        return 'application/octet-stream'
