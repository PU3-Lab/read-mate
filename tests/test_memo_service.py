"""memo_service 동작 테스트."""

from __future__ import annotations

from pathlib import Path

from services import memo_service


def test_save_and_load_summary_memo(monkeypatch, tmp_path: Path) -> None:
    """메모 저장 후 목록과 상세 조회가 가능해야 한다."""
    memo_root = tmp_path / 'memos'
    monkeypatch.setattr(memo_service, 'memos_path', lambda file_name='': memo_root / file_name if file_name else memo_root)

    saved = memo_service.save_summary_memo(
        summary='요약 첫 줄\n두 번째 줄',
        key_points=['핵심 1', '핵심 2'],
        raw_text='원문 전체',
        audio_bytes=b'wave-audio',
        audio_mime='audio/wav',
        audio_file_name='summary.wav',
        source_name='lecture-note.pdf',
    )

    memos = memo_service.list_saved_memos()
    detail = memo_service.load_saved_memo(saved['id'])

    assert len(memos) == 1
    assert memos[0]['id'] == saved['id']
    assert memos[0]['title'] == 'lecture-note'
    assert memos[0]['has_audio'] is True
    assert detail['summary'] == '요약 첫 줄\n두 번째 줄'
    assert detail['key_points'] == ['핵심 1', '핵심 2']
    assert detail['raw_text'] == '원문 전체'
    assert detail['audio_bytes'] == b'wave-audio'
    assert detail['audio_mime'] == 'audio/wav'
    assert (memo_root / saved['id'] / 'summary.txt').read_text(encoding='utf-8') == detail['summary']
    assert (memo_root / saved['id'] / 'summary.wav').read_bytes() == b'wave-audio'


def test_list_saved_memos_orders_newest_first(monkeypatch, tmp_path: Path) -> None:
    """목록은 최신 메모가 먼저 와야 한다."""
    memo_root = tmp_path / 'memos'
    monkeypatch.setattr(memo_service, 'memos_path', lambda file_name='': memo_root / file_name if file_name else memo_root)

    first = memo_service.save_summary_memo(summary='첫 번째 요약')
    second = memo_service.save_summary_memo(summary='두 번째 요약')

    memos = memo_service.list_saved_memos()

    assert [memo['id'] for memo in memos] == [second['id'], first['id']]


def test_save_summary_memo_skips_duplicate_content(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """같은 메모 내용은 중복 저장하지 않고 기존 항목을 반환해야 한다."""
    memo_root = tmp_path / 'memos'
    monkeypatch.setattr(
        memo_service,
        'memos_path',
        lambda file_name='': memo_root / file_name if file_name else memo_root,
    )

    first = memo_service.save_summary_memo(
        summary='같은 요약',
        key_points=['핵심'],
        raw_text='같은 원문',
    )
    second = memo_service.save_summary_memo(
        summary='같은 요약',
        key_points=['핵심'],
        raw_text='같은 원문',
    )

    memos = memo_service.list_saved_memos()

    assert first['id'] == second['id']
    assert len(memos) == 1
