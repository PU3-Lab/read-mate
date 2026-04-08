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
    t = text.lower()
    t = t.replace('backspace', '백스페이스')
    t = t.replace('space', '스페이스')
    t = t.replace('enter', '엔터')
    t = t.replace('tab', '탭')
    return ' '.join(t.split())


_TEXT_ALIASES: dict[str, str] = {
    normalize_tts_text(
        '리드메이트입니다. 소리로 읽는 강의자료, 배움의 끝이 없도록 우리 함께 공부해요. Tab키를 눌러 버튼으로 이동하세요. 첫번째 버튼은 강의 녹음 분석, 두번째 버튼은 강의 자료 분석, 세번째 버튼은 내 목소리 설정입니다. Enter 를 눌러 선택하세요.'
    ): normalize_tts_text(
        '리드메이트입니다. 소리로 읽는 강의자료, 배움의 끝이 없도록 우리 함께 공부해요. 탭키를 눌러 버튼으로 이동하세요. 첫번째 버튼은 강의 녹음 분석, 두번째 버튼은 강의 자료 분석, 세번째 버튼은 내 목소리 설정입니다. 엔터 를 눌러 선택하세요.'
    ),
    normalize_tts_text(
        '첫번째 버튼, 강의 녹음 분석입니다. Enter 를 누르면 시작합니다.'
    ): normalize_tts_text(
        '첫번째 버튼, 강의 녹음 분석입니다. 엔터를 누르면 시작합니다.'
    ),
    normalize_tts_text(
        '두번째 버튼, 강의 자료 분석입니다. Enter 를 누르면 시작합니다.'
    ): normalize_tts_text(
        '두번째 버튼, 강의 자료 분석입니다. 엔터를 누르면 시작합니다.'
    ),
    normalize_tts_text(
        '세번째 버튼, 내 목소리 설정입니다. Enter 를 누르면 시작합니다.'
    ): normalize_tts_text(
        '세번째 버튼, 내 목소리 설정입니다. 엔터를 누르면 시작합니다.'
    ),
    normalize_tts_text(
        '내 목소리 설정입니다. 화자 이름을 입력하고, WAV 파일을 업로드한 뒤 등록 버튼을 눌러주세요.'
    ): normalize_tts_text(
        '내 목소리 설정입니다. 화자 이름을 입력하고, 오디오 파일을 업로드한 뒤 등록 버튼을 눌러주세요.'
    ),
    normalize_tts_text(
        '녹음이 중지되었습니다. 전송하기 버튼을 누르세요.'
    ): normalize_tts_text(
        '녹음이 중지되었습니다. 엔터를 눌러 전송하세요.'
    ),
    normalize_tts_text(
        '질의응답 화면입니다. Space 를 눌러 질문을 하고, 다시 Space 로 중지한 뒤 Enter 로 전송하세요. Backspace 를 누르면 요약화면 으로 돌아갑니다.'
    ): normalize_tts_text(
        '질의응답 화면입니다. 스페이스키 를 눌러 질문을 하고, 다시 스페이크키 로 중지한 뒤 엔터키 로 전송하세요. 백스페이스 를 누르면 요약화면 으로 돌아갑니다.'
    ),
    normalize_tts_text(
        '1번, 파일 업로드 버튼입니다. Enter 를 눌러주세요.'
    ): normalize_tts_text(
        '일번, 파일 업로드 버튼입니다. 엔터를 눌러주세요.'
    ),
}


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
        normalized_text = _TEXT_ALIASES.get(normalized_text, normalized_text)
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
