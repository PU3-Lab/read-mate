"""
전체 TTS 엔진 실추론 매트릭스 테스트.

목적:
    - 현재 프로젝트에 등록된 모든 TTS 엔진을 한 번에 점검한다.
    - 엔진별 기본 화자 또는 전체 화자를 순회하며 오디오 생성 성공 여부를 확인한다.
    - API 키 미설정, 의존성 누락, 네트워크 이슈는 실패 대신 skip으로 집계한다.

실행 예시:
    uv run python tests/test_tts_models_real.py
    uv run python tests/test_tts_models_real.py --all-voices
    uv run python tests/test_tts_models_real.py --engine edge
    uv run python tests/test_tts_models_real.py --engine zonos --speaker-audio data/audio/ref.wav
    uv run python tests/test_tts_models_real.py --strict
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from pathlib import Path

from lib.utils.path import data_path
from services.tts_service import TTSService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

MIN_FILE_SIZE_BYTES = 1024
DEFAULT_TEXT = '안녕하세요. ReadMate 전체 TTS 엔진 점검 테스트입니다.'
SKIP_EXIT_CODE = 0
FAIL_EXIT_CODE = 1


def sanitize_filename(name: str) -> str:
    """화자 이름을 파일명으로 안전하게 변환한다."""
    sanitized = re.sub(r'[^A-Za-z0-9._-]+', '_', name.strip())
    return sanitized.strip('._') or 'voice'


def section(title: str) -> None:
    print(f'\n{"=" * 70}')
    print(title)
    print(f'{"=" * 70}')


def check(label: str, passed: bool, detail: str = '') -> bool:
    mark = 'PASS' if passed else 'FAIL'
    print(f'  [{mark}] {label}' + (f'  ({detail})' if detail else ''))
    return passed


def should_skip_exception(exc: Exception) -> bool:
    """환경 문제로 실행 불가능한 경우를 skip으로 취급한다."""
    message = str(exc).lower()
    skip_markers = [
        'api key',
        'not set',
        '설정되어 있지 않습니다',
        'import 실패',
        '로딩 실패',
        'connection',
        'network',
        'dns',
        'espeak',
        'ffmpeg',
        'model',
    ]
    return any(marker in message for marker in skip_markers)


def build_voice_plan(
    engine: str,
    service: TTSService,
    all_voices: bool,
    speaker_audio: str | None,
) -> list[str]:
    """
    엔진별 테스트할 화자 목록을 결정한다.

    Zonos는 고정 화자 목록이 없으므로 speaker_audio가 있으면 그 경로를 사용하고,
    없으면 default 1회만 실행한다.
    """
    if engine == 'zonos':
        return [speaker_audio] if speaker_audio else ['default']

    presets = service.list_presets()
    if not presets:
        return []
    return presets if all_voices else [presets[0]]


def synthesize_once(
    engine: str,
    voice_preset: str,
    text: str,
    output_dir: Path,
) -> dict[str, object]:
    """엔진 하나와 화자 하나를 실제로 합성한다."""
    service = TTSService(engine=engine)

    started_at = time.perf_counter()
    result = service.synthesize(text, voice_preset=voice_preset)
    elapsed = time.perf_counter() - started_at

    audio_path = Path(result.audio_path)
    suffix = audio_path.suffix.lstrip('.') or 'bin'
    dest_name = f'{engine}__{sanitize_filename(voice_preset)}.{suffix}'
    dest_path = output_dir / dest_name
    dest_path.write_bytes(audio_path.read_bytes())

    file_size = audio_path.stat().st_size if audio_path.exists() else 0
    ok = True
    ok &= check('오디오 파일 생성', audio_path.exists(), audio_path.name)
    ok &= check('파일 크기 충분', file_size >= MIN_FILE_SIZE_BYTES, f'{file_size} bytes')
    ok &= check('엔진명 반환', bool(result.engine), result.engine)
    ok &= check('화자명 반환', bool(result.voice_preset), result.voice_preset)

    print(f'  engine: {result.engine}')
    print(f'  voice:  {result.voice_preset}')
    print(f'  file:   {dest_path}')
    print(f'  time:   {result.duration_sec:.2f}s (wall: {elapsed:.2f}s)')

    return {
        'status': 'passed' if ok else 'failed',
        'engine': engine,
        'voice': voice_preset,
        'elapsed': round(elapsed, 2),
        'saved_to': str(dest_path),
    }


def run_engine(
    engine: str,
    text: str,
    output_dir: Path,
    all_voices: bool,
    speaker_audio: str | None,
) -> list[dict[str, object]]:
    """엔진 단위로 테스트를 실행한다."""
    section(f'ENGINE: {engine}')

    try:
        service = TTSService(engine=engine)
        voice_plan = build_voice_plan(engine, service, all_voices, speaker_audio)
    except Exception as exc:
        status = 'skipped' if should_skip_exception(exc) else 'failed'
        print(f'  [{status.upper()}] 엔진 준비 실패: {exc}')
        return [
            {
                'status': status,
                'engine': engine,
                'voice': '',
                'elapsed': 0.0,
                'error': str(exc),
            }
        ]

    if not voice_plan:
        print('  [SKIPPED] 테스트할 화자가 없습니다.')
        return [
            {
                'status': 'skipped',
                'engine': engine,
                'voice': '',
                'elapsed': 0.0,
                'error': '사용 가능한 화자 없음',
            }
        ]

    results: list[dict[str, object]] = []
    for voice_preset in voice_plan:
        print(f'\n  voice preset: {voice_preset}')
        try:
            result = synthesize_once(engine, voice_preset, text, output_dir)
        except Exception as exc:
            status = 'skipped' if should_skip_exception(exc) else 'failed'
            print(f'  [{status.upper()}] 합성 실패: {exc}')
            result = {
                'status': status,
                'engine': engine,
                'voice': voice_preset,
                'elapsed': 0.0,
                'error': str(exc),
            }
        results.append(result)

    return results


def print_summary(results: list[dict[str, object]]) -> tuple[int, int, int]:
    """최종 집계 출력."""
    section('SUMMARY')
    passed = failed = skipped = 0

    for item in results:
        status = str(item['status'])
        if status == 'passed':
            passed += 1
        elif status == 'failed':
            failed += 1
        else:
            skipped += 1

        detail = f'{item["engine"]}:{item["voice"] or "-"}'
        extra = item.get('error') or f'{item.get("elapsed", 0.0)}s'
        print(f'  {status.upper():7} {detail}  ({extra})')

    print(f'\n  passed={passed} failed={failed} skipped={skipped}')
    return passed, failed, skipped


def main() -> None:
    available = TTSService.available_engines()

    parser = argparse.ArgumentParser(description='전체 TTS 엔진 실추론 매트릭스 테스트')
    parser.add_argument(
        '--engine',
        choices=available,
        default=None,
        help='특정 엔진만 테스트',
    )
    parser.add_argument('--text', default=DEFAULT_TEXT, help='합성할 텍스트')
    parser.add_argument(
        '--all-voices',
        action='store_true',
        help='각 엔진의 전체 화자를 테스트',
    )
    parser.add_argument(
        '--speaker-audio',
        default=None,
        help='Zonos 화자 클로닝용 참조 오디오 경로',
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='skip도 실패로 간주하고 비정상 종료',
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=data_path() / 'tts_matrix_output',
        help='오디오 저장 디렉토리',
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    engines = [args.engine] if args.engine else available

    print('\nTTS matrix test start')
    print(f'  engines: {engines}')
    print(f'  all_voices: {args.all_voices}')
    print(f'  output_dir: {args.output_dir}')

    results: list[dict[str, object]] = []
    for engine in engines:
        results.extend(
            run_engine(
                engine=engine,
                text=args.text,
                output_dir=args.output_dir,
                all_voices=args.all_voices,
                speaker_audio=args.speaker_audio,
            )
        )

    _, failed, skipped = print_summary(results)
    if failed > 0:
        sys.exit(FAIL_EXIT_CODE)
    if args.strict and skipped > 0:
        sys.exit(FAIL_EXIT_CODE)
    sys.exit(SKIP_EXIT_CODE)


if __name__ == '__main__':
    main()
