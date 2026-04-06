"""
LLM 서버 실 테스트 (HTTP 클라이언트 사용).
서버가 실행 중인 상태에서 실행해야 한다.

실행:
    uv run python tests/test_llm_real.py
    uv run python tests/test_llm_real.py --qa
    uv run python tests/test_llm_real.py --sample science_climate
    uv run python tests/test_llm_real.py --url http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import logging
import time

from api.client import DEFAULT_BASE_URL, LLMClient
from lib.utils.path import data_path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

# ── 평가 기준 ───────────────────────────────────────────
MIN_SUMMARY_LEN = 30
MIN_KEY_POINTS = 2
MIN_QA_ANSWER_LEN = 10


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
# 요약 테스트
# ─────────────────────────────────────────────────────────────────


def run_summarize(client: LLMClient, key: str, sample: dict) -> dict:
    section(f'[{key}] {sample["label"]}')
    text = sample['text']
    print(f'  입력 길이: {len(text)}자')

    t0 = time.perf_counter()
    result = client.summarize(text)
    elapsed = time.perf_counter() - t0

    print(f'\n  [요약]\n  {result.summary}')
    print('\n  [핵심 포인트]')
    for i, kp in enumerate(result.key_points, 1):
        print(f'    {i}. {kp}')
    print(f'\n  ⏱  {elapsed:.2f}s | 엔진: {result.engine}')

    ok = check(
        'summary 길이',
        len(result.summary) >= MIN_SUMMARY_LEN,
        f'{len(result.summary)}자',
    )
    ok &= check(
        'key_points 개수',
        len(result.key_points) >= MIN_KEY_POINTS,
        f'{len(result.key_points)}개',
    )
    return {'passed': ok, 'elapsed': round(elapsed, 2)}


# ─────────────────────────────────────────────────────────────────
# QA 테스트
# ─────────────────────────────────────────────────────────────────


def run_qa(client: LLMClient, key: str, sample: dict) -> dict | None:
    question = sample.get('question')
    if not question:
        return None

    print(f'\n  ▶ QA: {question}')
    t0 = time.perf_counter()
    result = client.qa(sample['text'], question)
    elapsed = time.perf_counter() - t0

    print(f'  [답변] {result.qa_answer}')
    print(f'  ⏱  {elapsed:.2f}s')

    ok = check('qa_answer 존재', bool(result.qa_answer))
    ok &= check(
        'qa_answer 길이',
        len(result.qa_answer or '') >= MIN_QA_ANSWER_LEN,
        f'{len(result.qa_answer or "")}자',
    )
    return {'passed': ok, 'elapsed': round(elapsed, 2)}


# ─────────────────────────────────────────────────────────────────
# 결과 집계
# ─────────────────────────────────────────────────────────────────


def print_summary(all_results: dict) -> None:
    section('테스트 결과 요약')
    total, passed = 0, 0
    for key, tasks in all_results.items():
        for task, res in tasks.items():
            total += 1
            if res['passed']:
                passed += 1
            mark = '✅' if res['passed'] else '❌'
            print(f'  {mark} [{key}] {task}  ({res["elapsed"]}s)')

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
    parser = argparse.ArgumentParser(description='LLM 서버 실 테스트')
    parser.add_argument('--url', default=DEFAULT_BASE_URL, help=f'서버 URL (기본: {DEFAULT_BASE_URL})')

    with open(data_path() / 'sample_texts.json', encoding='utf-8') as f:
        samples_dict = json.loads(f.read())

    parser.add_argument(
        '--sample', choices=list(samples_dict.keys()), help='특정 샘플만 실행'
    )
    parser.add_argument('--qa', action='store_true', help='QA 테스트도 함께 실행')
    args = parser.parse_args()

    client = LLMClient(base_url=args.url)

    print('\n🚀 LLM 서버 테스트 시작')
    print(f'   서버: {args.url}')
    print(f'   모드: 요약{"+ QA" if args.qa else ""}')

    if not client.health():
        print(f'\n❌ 서버에 연결할 수 없습니다: {args.url}')
        print('   uv run uvicorn backend.main:app --port 8000 으로 서버를 먼저 실행하세요.')
        return

    targets = {args.sample: samples_dict[args.sample]} if args.sample else samples_dict

    all_results: dict = {}
    for key, sample in targets.items():
        all_results[key] = {}
        all_results[key]['summarize'] = run_summarize(client, key, sample)
        if args.qa:
            qa_res = run_qa(client, key, sample)
            if qa_res:
                all_results[key]['qa'] = qa_res

    print_summary(all_results)


if __name__ == '__main__':
    main()
