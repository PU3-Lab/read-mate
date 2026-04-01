"""
QwenLLM 실 추론 테스트.
실제 모델을 로드해 요약·질의응답 결과를 검증한다.

실행:
    uv run python tests/test_llm_real.py
    uv run python tests/test_llm_real.py --sample science_climate
    uv run python tests/test_llm_real.py --all
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from data.sample_texts import SAMPLES

from models.schemas import TaskType
from services.llm import QwenLLM

# ── 경로 설정 ───────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

# ── 평가 기준 ───────────────────────────────────────────────────
MIN_SUMMARY_LEN = 30  # 요약이 최소 30자 이상
MIN_KEY_POINTS = 2  # 핵심 포인트 최소 2개
MIN_QA_ANSWER_LEN = 10  # QA 답변 최소 10자


# ─────────────────────────────────────────────────────────────────
# 출력 헬퍼
# ─────────────────────────────────────────────────────────────────


def section(title: str) -> None:
    print(f'\n{"─" * 55}')
    print(f'  {title}')
    print(f'{"─" * 55}')


def check(label: str, passed: bool, detail: str = '') -> bool:
    mark = '✅' if passed else '❌'
    line = f'  {mark} {label}'
    if detail:
        line += f'  ({detail})'
    print(line)
    return passed


# ─────────────────────────────────────────────────────────────────
# 단일 샘플 테스트
# ─────────────────────────────────────────────────────────────────


def run_sample(llm: QwenLLM, key: str, sample: dict) -> dict:
    label = sample['label']
    text = sample['text']
    question = sample.get('question')

    section(f'[{key}] {label}')
    print(f'  입력 길이: {len(text)}자')
    if question:
        print(f'  질문: {question}')

    results = {}

    # ── 1. 요약 테스트 ──────────────────────────────────────────
    print('\n  ▶ SUMMARIZE')
    t0 = time.perf_counter()
    result = llm.generate(text, TaskType.SUMMARIZE)
    elapsed = time.perf_counter() - t0

    print(f'\n  [요약]\n  {result.summary}')
    print('\n  [핵심 포인트]')
    for i, kp in enumerate(result.key_points, 1):
        print(f'    {i}. {kp}')
    print(f'\n  ⏱  {elapsed:.2f}s | 엔진: {result.engine}')

    ok_summary = check(
        'summary 길이',
        len(result.summary) >= MIN_SUMMARY_LEN,
        f'{len(result.summary)}자',
    )
    ok_kp = check(
        'key_points 개수',
        len(result.key_points) >= MIN_KEY_POINTS,
        f'{len(result.key_points)}개',
    )
    results['summarize'] = {
        'passed': ok_summary and ok_kp,
        'elapsed': round(elapsed, 2),
    }

    # ── 2. QA 테스트 ────────────────────────────────────────────
    if question:
        print('\n  ▶ QA')
        t0 = time.perf_counter()
        qa_result = llm.generate(text, TaskType.QA, question=question)
        elapsed = time.perf_counter() - t0

        print(f'\n  [질문] {question}')
        print(f'  [답변] {qa_result.qa_answer}')
        print(f'\n  ⏱  {elapsed:.2f}s')

        ok_qa = check('qa_answer 존재', bool(qa_result.qa_answer))
        ok_qa_len = check(
            'qa_answer 길이',
            len(qa_result.qa_answer or '') >= MIN_QA_ANSWER_LEN,
            f'{len(qa_result.qa_answer or "")}자',
        )
        results['qa'] = {'passed': ok_qa and ok_qa_len, 'elapsed': round(elapsed, 2)}

    return results


# ─────────────────────────────────────────────────────────────────
# 전체 결과 집계
# ─────────────────────────────────────────────────────────────────


def print_summary(all_results: dict) -> None:
    section('테스트 결과 요약')
    total = 0
    passed = 0
    for key, tasks in all_results.items():
        for task, res in tasks.items():
            total += 1
            if res['passed']:
                passed += 1
            mark = '✅' if res['passed'] else '❌'
            print(f'  {mark} [{key}] {task}  ({res["elapsed"]}s)')

    print(f'\n  결과: {passed}/{total} 통과')
    if passed == total:
        print('\n  🎉 모든 테스트 통과!')
    else:
        print(f'\n  ⚠️  {total - passed}개 실패. 로그를 확인하세요.')


# ─────────────────────────────────────────────────────────────────
# 진입점
# ─────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description='QwenLLM 실 추론 테스트')
    parser.add_argument(
        '--sample', choices=list(SAMPLES.keys()), help='특정 샘플만 실행'
    )
    parser.add_argument('--all', action='store_true', help='전체 샘플 실행 (기본값)')
    parser.add_argument(
        '--model',
        default='Qwen/Qwen2.5-7B-Instruct',
        help='사용할 모델명 (기본: Qwen2.5-7B-Instruct)',
    )
    args = parser.parse_args()

    print('\n🚀 QwenLLM 실 테스트 시작')
    print(f'   모델: {args.model}')

    t_load = time.perf_counter()
    llm = QwenLLM(model_name=args.model)
    print(f'   모델 로드: {time.perf_counter() - t_load:.1f}s')

    targets = {args.sample: SAMPLES[args.sample]} if args.sample else SAMPLES

    all_results: dict = {}
    for key, sample in targets.items():
        all_results[key] = run_sample(llm, key, sample)

    print_summary(all_results)


if __name__ == '__main__':
    main()
