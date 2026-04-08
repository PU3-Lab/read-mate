"""
ElevenLabs TTS 테스트 스크립트.

사용법:
    uv run test_elevenlabs.py
    uv run test_elevenlabs.py --text "읽어줄 텍스트"
    uv run test_elevenlabs.py --text "읽어줄 텍스트" --voice "Narae"
    uv run test_elevenlabs.py --list
"""

from __future__ import annotations

import argparse
import subprocess
import sys

sys.path.insert(0, 'src')

from services.tts_elevenlabs import ElevenLabsTTS

DEFAULT_TEXT = '안녕하세요. 저는 ReadMate입니다. 문서를 읽어드리는 학습 보조 도구입니다.'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='ElevenLabs TTS 테스트')
    parser.add_argument('--text', '-t', default=DEFAULT_TEXT, help='합성할 텍스트')
    parser.add_argument('--voice', '-v', default='Narae', help='화자 이름 (기본값: Narae)')
    parser.add_argument('--list', '-l', action='store_true', help='사용 가능한 화자 목록 출력')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tts = ElevenLabsTTS()

    if args.list:
        presets = tts.list_presets()
        print(f'화자 목록 ({len(presets)}명):')
        for name in presets:
            print(f'  - {name}')
        return

    print(f'텍스트: {args.text}')
    print(f'화자:   {args.voice}')
    print('합성 중...')

    result = tts.synthesize(text=args.text, voice_preset=args.voice)

    print(f'완료:   {result.duration_sec}s')
    print(f'파일:   {result.audio_path}')

    # 자동 재생 (macOS: afplay, Linux: aplay, 없으면 경로만 출력)
    players = ['afplay', 'aplay', 'ffplay']
    for player in players:
        try:
            subprocess.run(
                [player, result.audio_path],
                check=True,
                capture_output=True,
            )
            break
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    else:
        print('재생기를 찾을 수 없습니다. 위 파일 경로를 직접 열어주세요.')


if __name__ == '__main__':
    main()
