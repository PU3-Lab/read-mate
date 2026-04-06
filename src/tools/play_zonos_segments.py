"""
Zonos 세그먼트 순차 재생 CLI.

긴 한국어 문장을 현재 Zonos 분할 규칙대로 나눈 뒤,
세그먼트별로 생성하고 바로 재생한다.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from services.tts_service import TTSService
from services.tts_zonos import ZonosEngine


def parse_args() -> argparse.Namespace:
    """CLI 인자를 파싱한다."""
    parser = argparse.ArgumentParser(
        description='긴 텍스트를 Zonos 세그먼트 단위로 생성하고 순차 재생한다.',
    )
    parser.add_argument(
        '--speaker-audio',
        required=True,
        help='Zonos 보이스 이름 또는 .pt/.wav 경로',
    )
    parser.add_argument(
        '--text',
        default='',
        help='합성할 텍스트',
    )
    parser.add_argument(
        '--text-file',
        default='',
        help='텍스트 파일 경로(.txt, utf-8)',
    )
    parser.add_argument(
        '--start',
        type=int,
        default=1,
        help='재생 시작 세그먼트 번호(1-based)',
    )
    parser.add_argument(
        '--end',
        type=int,
        default=0,
        help='재생 종료 세그먼트 번호(0이면 끝까지)',
    )
    parser.add_argument(
        '--allow-mps',
        action='store_true',
        help='Zonos MPS 강제 사용',
    )
    return parser.parse_args()


def resolve_text(args: argparse.Namespace) -> str:
    """인자에서 텍스트를 읽는다."""
    if args.text_file:
        return Path(args.text_file).expanduser().read_text(encoding='utf-8').strip()
    return args.text.strip()


def resolve_audio_player() -> list[str] | None:
    """현재 환경에서 사용할 수 있는 오디오 플레이어를 찾는다."""
    for command in (['afplay'], ['ffplay', '-nodisp', '-autoexit'], ['play']):
        if shutil.which(command[0]):
            return command
    return None


def play_audio_file(audio_path: Path) -> None:
    """오디오 파일을 즉시 재생한다."""
    command = resolve_audio_player()
    if command is None:
        raise RuntimeError(
            '재생 가능한 오디오 플레이어를 찾지 못했습니다. '
            'macOS는 afplay, 그 외 환경은 ffplay/play 설치가 필요합니다.'
        )
    subprocess.run([*command, str(audio_path)], check=True)


def main() -> int:
    """CLI 진입점."""
    args = parse_args()
    text = resolve_text(args)
    if not text:
        print('텍스트가 비어 있습니다. --text 또는 --text-file 중 하나를 지정하세요.')
        return 1

    if args.allow_mps:
        os.environ['ZONOS_ALLOW_MPS'] = '1'

    segments = ZonosEngine._split_text_into_segments(text)
    start = max(1, args.start)
    end = args.end if args.end > 0 else len(segments)
    selected = segments[start - 1 : end]

    if not selected:
        print('선택된 세그먼트가 없습니다.')
        return 1

    service = TTSService(engine='zonos')
    print(f'Zonos segment play start total={len(segments)} range={start}-{end}')

    for idx, segment in enumerate(selected, start=start):
        print(f'\n[{idx}/{len(segments)}] {segment}')
        result = service.synthesize(segment, voice_preset=args.speaker_audio)
        audio_path = Path(result.audio_path)
        print(f'  file: {audio_path}')
        play_audio_file(audio_path)

    print('\ncompleted')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
