"""
TTS 실 추론 테스트.

실행:
    uv run python tests/test_tts_real.py                             # mms 기본 테스트
    uv run python tests/test_tts_real.py --engine mms                # MMS-TTS 한국어
    uv run python tests/test_tts_real.py --engine edge               # Edge TTS 한국어
    uv run python tests/test_tts_real.py --engine elevenlabs         # ElevenLabs API
    uv run python tests/test_tts_real.py --voice "InJoon"            # 특정 목소리 지정
    uv run python tests/test_tts_real.py --text "안녕하세요"          # 커스텀 텍스트
    uv run python tests/test_tts_real.py --all-voices                # 전체 화자 순차 테스트
    uv run python tests/test_tts_real.py --all-engines               # 전체 엔진 기본 화자 테스트

합성된 오디오는 data/tts_output/ 에 저장된다.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from lib.utils.path import data_path
from services.tts_factory import TTSFactory
from services.tts_service import TTSService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

MIN_FILE_SIZE_BYTES = 1024
DEFAULT_TEXT = '안녕하세요. ReadMate TTS 실 추론 테스트입니다. 음성이 잘 들리시나요?'


def section(title: str) -> None:
    print(f'\n{"─" * 55}')
    print(f'  {title}')
    print(f'{"─" * 55}')


def check(label: str, passed: bool, detail: str = '') -> bool:
    mark = '✅' if passed else '❌'
    print(f'  {mark} {label}' + (f'  ({detail})' if detail else ''))
    return passed


def run_synthesize(
    service: TTSService,
    text: str,
    voice_preset: str,
    output_dir: Path,
) -> dict:
    """
    텍스트 하나를 TTS 합성하고 결과를 검증한다.

    Args:
        service: TTSService 인스턴스
        text: 합성할 텍스트
        voice_preset: 프리셋 목소리 이름
        output_dir: 오디오 출력 디렉토리

    Returns:
        dict: passed(bool), elapsed(float) 포함 결과
    """
    section(f'목소리: {voice_preset}')
    print(f'  텍스트: {text[:50]}{"..." if len(text) > 50 else ""}')

    t0 = time.perf_counter()
    result = service.synthesize(text, voice_preset=voice_preset)
    elapsed = time.perf_counter() - t0

    audio_path = Path(result.audio_path)
    suffix = audio_path.suffix.lstrip('.')
    dest = output_dir / f'{voice_preset.replace(" ", "_")}_{suffix}.{suffix}'
    dest.write_bytes(audio_path.read_bytes())
    file_size = audio_path.stat().st_size

    print(f'\n  [결과]')
    print(f'  엔진:      {result.engine}')
    print(f'  목소리:    {result.voice_preset}')
    print(f'  파일:      {audio_path.name}  ({file_size / 1024:.1f} KB)')
    print(f'  합성 시간: {result.duration_sec:.2f}s  (총 경과: {elapsed:.2f}s)')
    print(f'  저장 위치: {dest}')

    ok = check('오디오 파일 생성됨', audio_path.exists(), audio_path.name)
    ok &= check('파일 크기 충분', file_size >= MIN_FILE_SIZE_BYTES, f'{file_size / 1024:.1f} KB')
    ok &= check('엔진 이름 반환됨', bool(result.engine), result.engine)
    ok &= check('목소리 반환됨', bool(result.voice_preset), result.voice_preset)

    return {'passed': ok, 'elapsed': round(elapsed, 2), 'voice': voice_preset}


def print_summary(all_results: dict) -> None:
    section('테스트 결과 요약')
    total, passed = 0, 0
    for name, res in all_results.items():
        total += 1
        if res['passed']:
            passed += 1
        mark = '✅' if res['passed'] else '❌'
        print(f'  {mark} {name}  ({res["elapsed"]}s)')
    print(f'\n  결과: {passed}/{total} 통과')
    print(
        '\n  모든 테스트 통과!'
        if passed == total
        else f'\n  {total - passed}개 실패.'
    )


def main() -> None:
    available = TTSFactory.available()
    parser = argparse.ArgumentParser(description='TTS 실 추론 테스트')
    parser.add_argument(
        '--engine',
        choices=available,
        default='mms',
        help=f'TTS 엔진 선택 (기본: mms) / 선택지: {available}',
    )
    parser.add_argument('--voice', default=None, help='목소리 프리셋 이름')
    parser.add_argument('--text', default=DEFAULT_TEXT, help='합성할 텍스트')
    parser.add_argument('--all-voices', action='store_true', help='전체 화자 순차 테스트')
    parser.add_argument('--all-engines', action='store_true', help='전체 엔진 기본 화자 테스트')
    args = parser.parse_args()

    output_dir = data_path() / 'tts_output'
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.all_engines:
        _run_all_engines(args.text, output_dir, available)
        return

    print('\n🚀 TTS 실 테스트 시작')
    print(f'   엔진: {args.engine}')

    t_load = time.perf_counter()
    try:
        service = TTSService(engine=args.engine)
    except ValueError as exc:
        print(f'\n❌ {exc}')
        sys.exit(1)
    print(f'   엔진 준비 완료: {time.perf_counter() - t_load:.1f}s')

    available_voices = service.list_presets()
    default_voice = available_voices[0]

    if args.all_voices:
        voices = available_voices
    elif args.voice:
        if args.voice not in available_voices:
            print(f'\n⚠️  알 수 없는 목소리: {args.voice!r}')
            print(f'   사용 가능: {available_voices}')
            sys.exit(1)
        voices = [args.voice]
    else:
        voices = [default_voice]

    print(f'   사용 가능한 목소리: {available_voices}')
    print(f'   테스트 목소리 수: {len(voices)}개')
    print(f'   출력 디렉토리: {output_dir}')

    all_results: dict = {}
    for voice in voices:
        try:
            res = run_synthesize(service, args.text, voice, output_dir)
            all_results[voice] = res
        except Exception as exc:
            print(f'\n  ❌ 합성 실패: {exc}')
            all_results[voice] = {'passed': False, 'elapsed': 0.0, 'voice': voice}

    print_summary(all_results)


def _run_all_engines(text: str, output_dir: Path, engines: list[str]) -> None:
    """전체 엔진을 기본 화자로 순차 테스트한다."""
    section('전체 엔진 테스트')
    all_results: dict = {}
    for engine in engines:
        print(f'\n  [엔진: {engine}]')
        try:
            service = TTSService(engine=engine)
            voice = service.list_presets()[0]
            res = run_synthesize(service, text, voice, output_dir)
            all_results[engine] = res
        except Exception as exc:
            print(f'  ❌ {engine} 실패: {exc}')
            all_results[engine] = {'passed': False, 'elapsed': 0.0, 'voice': ''}
    print_summary(all_results)


if __name__ == '__main__':
    main()
