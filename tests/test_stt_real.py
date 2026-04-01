"""
STT 실 추론 테스트 (faster-whisper).

실행:
    uv run python tests/test_stt_real.py                          # data/audio/ 전체 파일
    uv run python tests/test_stt_real.py --file path/to/audio.mp3 # 특정 파일 지정
    uv run python tests/test_stt_real.py --model medium           # 모델 크기 변경
    uv run python tests/test_stt_real.py --verbose                # 세그먼트 상세 출력

지원 포맷: .mp3 .wav .m4a .flac .ogg .webm
data/audio/ 디렉토리에 오디오 파일을 넣고 실행하거나,
--file 로 직접 경로를 지정한다.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from lib.utils.path import data_path
from services.stt_service import FasterWhisperEngine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

# ── 평가 기준 ────────────────────────────────────────────────────
MIN_TEXT_LEN = 5       # 최소 인식 문자 수
MIN_SEGMENTS = 1       # 최소 세그먼트 수
SUPPORTED_EXTS = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.webm'}


# ─────────────────────────────────────────────────────────────────
# 출력 헬퍼
# ─────────────────────────────────────────────────────────────────


def section(title: str) -> None:
    print(f'\n{"─" * 55}')
    print(f'  {title}')
    print(f'{"─" * 55}')


def check(label: str, passed: bool, detail: str = '') -> bool:
    mark = '✅' if passed else '❌'
    print(f'  {mark} {label}' + (f'  ({detail})' if detail else ''))
    return passed


# ─────────────────────────────────────────────────────────────────
# STT 단일 파일 테스트
# ─────────────────────────────────────────────────────────────────


def run_transcribe(
    engine: FasterWhisperEngine,
    audio_path: Path,
    verbose: bool = False,
) -> dict:
    """
    오디오 파일 하나를 STT 변환하고 결과를 출력한다.

    Args:
        engine: FasterWhisperEngine 인스턴스
        audio_path: 오디오 파일 경로
        verbose: True면 세그먼트 단위로 상세 출력

    Returns:
        dict: passed(bool), elapsed(float) 포함 결과
    """
    section(audio_path.name)
    size_kb = audio_path.stat().st_size / 1024
    print(f'  파일 크기: {size_kb:.1f} KB')

    audio_bytes = audio_path.read_bytes()

    t0 = time.perf_counter()
    result = engine.transcribe(audio_bytes)
    elapsed = time.perf_counter() - t0

    # 전체 텍스트 출력
    print(f'\n  [인식 텍스트]\n  {result.text or "(비어 있음)"}')
    print(f'\n  언어: {result.language}  |  세그먼트: {len(result.segments)}개  |  ⏱ {elapsed:.2f}s')
    print(f'  엔진: {result.engine}')

    # 세그먼트 상세
    if verbose and result.segments:
        print('\n  [세그먼트]')
        for seg in result.segments:
            print(f'    [{seg.start:.1f}s → {seg.end:.1f}s]  {seg.text}')

    # 검증
    ok = check('텍스트 비어있지 않음', len(result.text) >= MIN_TEXT_LEN, f'{len(result.text)}자')
    ok &= check('세그먼트 존재', len(result.segments) >= MIN_SEGMENTS, f'{len(result.segments)}개')
    ok &= check('언어 감지됨', bool(result.language), result.language)

    return {'passed': ok, 'elapsed': round(elapsed, 2), 'chars': len(result.text)}


# ─────────────────────────────────────────────────────────────────
# 결과 집계
# ─────────────────────────────────────────────────────────────────


def print_summary(all_results: dict) -> None:
    section('테스트 결과 요약')
    total, passed = 0, 0
    for name, res in all_results.items():
        total += 1
        if res['passed']:
            passed += 1
        mark = '✅' if res['passed'] else '❌'
        print(f'  {mark} {name}  ({res["elapsed"]}s, {res["chars"]}자)')

    print(f'\n  결과: {passed}/{total} 통과')
    print(
        '\n  🎉 모든 테스트 통과!'
        if passed == total
        else f'\n  ⚠️  {total - passed}개 실패.'
    )


# ─────────────────────────────────────────────────────────────────
# 진입점
# ─────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description='STT 실 추론 테스트')
    parser.add_argument(
        '--file',
        type=Path,
        default=None,
        help='특정 오디오 파일 경로 (미지정 시 data/audio/ 전체)',
    )
    parser.add_argument(
        '--model',
        default=None,
        help='faster-whisper 모델 크기 (tiny/base/small/medium/large-v3, 기본: config 값)',
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='세그먼트 단위 상세 출력',
    )
    args = parser.parse_args()

    # 오디오 파일 목록 결정
    if args.file:
        if not args.file.exists():
            print(f'❌ 파일을 찾을 수 없습니다: {args.file}')
            sys.exit(1)
        audio_files = [args.file]
    else:
        audio_dir = data_path() / 'audio'
        audio_dir.mkdir(exist_ok=True)
        audio_files = [f for f in audio_dir.iterdir() if f.suffix.lower() in SUPPORTED_EXTS]

        if not audio_files:
            print(f'\n⚠️  테스트할 오디오 파일이 없습니다.')
            print(f'   {audio_dir} 에 파일을 넣거나 --file 로 직접 지정하세요.')
            print(f'   지원 포맷: {", ".join(sorted(SUPPORTED_EXTS))}')
            sys.exit(1)

        audio_files.sort(key=lambda f: f.name)

    print('\n🚀 STT 실 테스트 시작')
    print(f'   파일 수: {len(audio_files)}개')

    # 모델 로드
    kwargs = {'model_size': args.model} if args.model else {}
    t_load = time.perf_counter()
    engine = FasterWhisperEngine(**kwargs)
    print(f'   모델 준비 완료: {time.perf_counter() - t_load:.1f}s')

    # 테스트 실행
    all_results: dict = {}
    for audio_path in audio_files:
        all_results[audio_path.name] = run_transcribe(engine, audio_path, verbose=args.verbose)

    print_summary(all_results)


if __name__ == '__main__':
    main()
