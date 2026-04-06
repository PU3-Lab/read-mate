"""
Zonos 보이스 라이브러리 일괄 등록 CLI.

참조 오디오 파일 또는 폴더를 받아 speaker embedding(.pt)으로 저장한다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config import ZONOS_EMBEDDINGS_DIR
from services.tts_service import TTSService

SUPPORTED_EXTENSIONS = {'.wav', '.mp3', '.m4a', '.flac', '.ogg'}


def parse_args() -> argparse.Namespace:
    """CLI 인자를 파싱한다."""
    parser = argparse.ArgumentParser(
        description='참조 오디오를 Zonos 보이스 라이브러리로 일괄 등록한다.',
    )
    parser.add_argument(
        'inputs',
        nargs='+',
        help='등록할 오디오 파일 또는 폴더 경로',
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='같은 이름의 기존 보이스가 있어도 덮어쓴다.',
    )
    parser.add_argument(
        '--recursive',
        action='store_true',
        help='폴더 입력을 하위 폴더까지 재귀 탐색한다.',
    )
    return parser.parse_args()


def is_supported_audio(path: Path) -> bool:
    """지원하는 오디오 확장자인지 확인한다."""
    return path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS


def collect_audio_files(inputs: list[str], recursive: bool) -> list[Path]:
    """입력 파일/폴더에서 등록 대상 오디오 파일 목록을 수집한다."""
    files: list[Path] = []
    for raw in inputs:
        path = Path(raw).expanduser()
        if path.is_file():
            if is_supported_audio(path):
                files.append(path)
            continue

        if not path.is_dir():
            continue

        iterator = path.rglob('*') if recursive else path.glob('*')
        for candidate in iterator:
            if is_supported_audio(candidate):
                files.append(candidate)

    return sorted(set(files))


def target_embedding_path(source: Path) -> Path:
    """참조 오디오 파일명 기준으로 저장될 .pt 경로를 계산한다."""
    return ZONOS_EMBEDDINGS_DIR / f'{source.stem}.pt'


def main() -> int:
    """CLI 진입점."""
    args = parse_args()
    service = TTSService(engine='zonos')
    audio_files = collect_audio_files(args.inputs, recursive=args.recursive)

    if not audio_files:
        print('등록할 오디오 파일을 찾지 못했습니다.')
        return 1

    saved = 0
    skipped = 0

    print(f'Zonos voice register start ({len(audio_files)} files)')
    for source in audio_files:
        target = target_embedding_path(source)
        if target.exists() and not args.overwrite:
            skipped += 1
            print(f'  [SKIP] {source} -> {target.name} (already exists)')
            continue

        result = service.save_voice(str(source), source.stem)
        saved += 1
        print(f'  [SAVE] {source} -> {result}')

    print(f'completed saved={saved} skipped={skipped} dir={ZONOS_EMBEDDINGS_DIR}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
