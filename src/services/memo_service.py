"""요약 메모 저장과 조회를 담당한다."""

from __future__ import annotations

import json
import hashlib
import mimetypes
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from lib.utils.path import memos_path


class MemoListItem(TypedDict):
    """메모 목록 렌더링에 필요한 최소 정보."""

    id: str
    title: str
    created_at: str
    source_name: str
    has_audio: bool


class MemoDetail(MemoListItem):
    """메모 상세 표시와 재생에 필요한 정보."""

    summary: str
    key_points: list[str]
    raw_text: str
    audio_bytes: bytes | None
    audio_mime: str | None
    audio_file_name: str | None


def save_summary_memo(
    summary: str,
    key_points: list[str] | tuple[str, ...] | str | None = None,
    raw_text: str = '',
    audio_bytes: bytes | None = None,
    audio_mime: str | None = None,
    audio_file_name: str | None = None,
    source_name: str = '',
) -> MemoListItem:
    """요약 메모를 로컬 디스크에 저장한다."""
    cleaned_summary = str(summary).strip()
    if not cleaned_summary:
        raise ValueError('summary must not be empty')

    normalized_key_points = _normalize_key_points(key_points)
    duplicate_signature = _build_duplicate_signature(
        summary=cleaned_summary,
        raw_text=raw_text,
        key_points=normalized_key_points,
    )
    existing_item = _find_existing_memo(duplicate_signature)
    if existing_item is not None:
        return existing_item

    memo_id = uuid.uuid4().hex
    created_at = datetime.now(UTC).isoformat()
    memo_dir = _memo_dir(memo_id)
    memo_dir.mkdir(parents=True, exist_ok=True)

    summary_file_name = 'summary.txt'
    (memo_dir / summary_file_name).write_text(cleaned_summary, encoding='utf-8')

    raw_text_file_name = ''
    cleaned_raw_text = str(raw_text).strip()
    if cleaned_raw_text:
        raw_text_file_name = 'raw_text.txt'
        (memo_dir / raw_text_file_name).write_text(cleaned_raw_text, encoding='utf-8')

    saved_audio_file_name = ''
    saved_audio_mime = audio_mime or ''
    if audio_bytes:
        saved_audio_file_name = _normalize_audio_file_name(audio_file_name, audio_mime)
        (memo_dir / saved_audio_file_name).write_bytes(audio_bytes)
        if not saved_audio_mime:
            saved_audio_mime, _ = mimetypes.guess_type(saved_audio_file_name)
            saved_audio_mime = saved_audio_mime or 'application/octet-stream'

    metadata = {
        'id': memo_id,
        'title': _build_title(cleaned_summary, source_name),
        'created_at': created_at,
        'source_name': str(source_name).strip(),
        'summary_file': summary_file_name,
        'raw_text_file': raw_text_file_name,
        'audio_file': saved_audio_file_name,
        'audio_mime': saved_audio_mime,
        'key_points': normalized_key_points,
        'duplicate_signature': duplicate_signature,
    }
    (memo_dir / 'memo.json').write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    return _to_list_item(metadata)


def list_saved_memos() -> list[MemoListItem]:
    """저장된 메모 목록을 최신순으로 반환한다."""
    items: list[MemoListItem] = []
    for metadata in _iter_memo_metadata():
        items.append(_to_list_item(metadata))
    return sorted(items, key=lambda item: item['created_at'], reverse=True)


def load_saved_memo(memo_id: str) -> MemoDetail:
    """저장된 메모 한 건을 읽어 상세 정보로 반환한다."""
    memo_dir = _memo_dir(memo_id)
    metadata = _read_metadata(memo_dir)
    if not metadata:
        raise FileNotFoundError(f'memo not found: {memo_id}')

    summary_file = str(metadata.get('summary_file') or 'summary.txt').strip()
    raw_text_file = str(metadata.get('raw_text_file') or '').strip()
    audio_file = str(metadata.get('audio_file') or '').strip()

    summary_path = memo_dir / summary_file
    if not summary_path.exists():
        raise FileNotFoundError(f'summary file not found: {summary_path}')

    raw_text = ''
    if raw_text_file:
        raw_text_path = memo_dir / raw_text_file
        if raw_text_path.exists():
            raw_text = raw_text_path.read_text(encoding='utf-8')

    audio_bytes: bytes | None = None
    if audio_file:
        audio_path = memo_dir / audio_file
        if audio_path.exists():
            audio_bytes = audio_path.read_bytes()

    return MemoDetail(
        id=str(metadata['id']),
        title=str(metadata.get('title') or '이름 없는 메모'),
        created_at=str(metadata.get('created_at') or ''),
        source_name=str(metadata.get('source_name') or ''),
        has_audio=bool(audio_file and audio_bytes),
        summary=summary_path.read_text(encoding='utf-8'),
        key_points=_normalize_key_points(metadata.get('key_points')),
        raw_text=raw_text,
        audio_bytes=audio_bytes,
        audio_mime=str(metadata.get('audio_mime') or '') or None,
        audio_file_name=audio_file or None,
    )


def _memo_dir(memo_id: str) -> Path:
    """메모 ID에 대응하는 디렉터리 경로를 반환한다."""
    cleaned_id = str(memo_id).strip()
    if not cleaned_id:
        raise ValueError('memo_id must not be empty')
    return memos_path(cleaned_id)


def _read_metadata(memo_dir: Path) -> dict[str, object] | None:
    """메모 디렉터리에서 메타데이터를 읽는다."""
    metadata_path = memo_dir / 'memo.json'
    if not metadata_path.exists():
        return None

    try:
        payload = json.loads(metadata_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None
    return payload


def _iter_memo_metadata() -> list[dict[str, object]]:
    """유효한 메모 메타데이터를 모두 반환한다."""
    items: list[dict[str, object]] = []
    for memo_dir in memos_path().iterdir():
        if not memo_dir.is_dir():
            continue
        metadata = _read_metadata(memo_dir)
        if not metadata:
            continue
        items.append(metadata)
    return items


def _normalize_audio_file_name(
    audio_file_name: str | None,
    audio_mime: str | None,
) -> str:
    """저장용 오디오 파일명을 안전하게 정규화한다."""
    candidate = Path(str(audio_file_name or '').strip()).name
    if candidate:
        return candidate

    guessed_ext = mimetypes.guess_extension(audio_mime or '') or '.wav'
    return f'summary_audio{guessed_ext}'


def _normalize_key_points(
    key_points: list[str] | tuple[str, ...] | str | object | None,
) -> list[str]:
    """메모 핵심 포인트를 문자열 목록으로 정리한다."""
    if key_points is None:
        return []
    if isinstance(key_points, str):
        values = key_points.replace('\n', ',').split(',')
    elif isinstance(key_points, (list, tuple)):
        values = list(key_points)
    else:
        values = [str(key_points)]

    return [text for text in (str(item).strip() for item in values) if text]


def _build_duplicate_signature(
    summary: str,
    raw_text: str,
    key_points: list[str],
) -> str:
    """같은 메모 여부를 판별할 시그니처를 생성한다."""
    normalized_summary = ' '.join(str(summary).split())
    normalized_raw_text = ' '.join(str(raw_text).split())
    normalized_key_points = '|'.join(' '.join(point.split()) for point in key_points)
    payload = '\n'.join([normalized_summary, normalized_raw_text, normalized_key_points])
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _find_existing_memo(duplicate_signature: str) -> MemoListItem | None:
    """같은 메모가 이미 저장되어 있으면 해당 목록 항목을 반환한다."""
    for metadata in _iter_memo_metadata():
        existing_signature = str(metadata.get('duplicate_signature') or '').strip()
        if existing_signature:
            if existing_signature == duplicate_signature:
                return _to_list_item(metadata)
            continue

        memo_dir = _memo_dir(str(metadata.get('id') or ''))
        summary_file = str(metadata.get('summary_file') or 'summary.txt').strip()
        raw_text_file = str(metadata.get('raw_text_file') or '').strip()
        summary_path = memo_dir / summary_file
        if not summary_path.exists():
            continue

        raw_text = ''
        if raw_text_file:
            raw_text_path = memo_dir / raw_text_file
            if raw_text_path.exists():
                raw_text = raw_text_path.read_text(encoding='utf-8')

        fallback_signature = _build_duplicate_signature(
            summary=summary_path.read_text(encoding='utf-8'),
            raw_text=raw_text,
            key_points=_normalize_key_points(metadata.get('key_points')),
        )
        if fallback_signature == duplicate_signature:
            return _to_list_item(metadata)
    return None


def _build_title(summary: str, source_name: str) -> str:
    """메모 목록용 제목을 생성한다."""
    cleaned_source = Path(str(source_name).strip()).stem
    if cleaned_source:
        return cleaned_source

    first_line = summary.splitlines()[0].strip()
    if len(first_line) <= 24:
        return first_line
    return f'{first_line[:24].rstrip()}...'


def _to_list_item(metadata: dict[str, object]) -> MemoListItem:
    """메타데이터를 목록 표시 구조로 변환한다."""
    audio_file = str(metadata.get('audio_file') or '').strip()
    return MemoListItem(
        id=str(metadata.get('id') or ''),
        title=str(metadata.get('title') or '이름 없는 메모'),
        created_at=str(metadata.get('created_at') or ''),
        source_name=str(metadata.get('source_name') or ''),
        has_audio=bool(audio_file),
    )
