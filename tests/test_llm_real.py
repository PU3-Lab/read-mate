"""
LLM 실 추론 테스트 (Gemma / Qwen / OpenAI 선택 가능).
기본: 텍스트 → 요약 (질문 없음)
QA:   --qa 플래그로 별도 실행

실행:
    uv run python tests/test_llm_real.py                          # Gemma, 전체 요약
    uv run python tests/test_llm_real.py --engine gemma
    uv run python tests/test_llm_real.py --engine gpt             # GPT, 전체 요약
    uv run python tests/test_llm_real.py --sample science_climate
    uv run python tests/test_llm_real.py --qa                     # 요약 + QA
    uv run python tests/test_llm_real.py --engine gemma --model google/gemma-3-12b-it
    uv run python tests/test_llm_real.py --engine qwen --model Qwen/Qwen2.5-14B-Instruct
    uv run python tests/test_llm_real.py --engine gpt  --model gpt-4.1
"""

from __future__ import annotations

import argparse
import json
import logging
import time

from lib.utils.path import data_path
from models.schemas import TaskType
from services.llm_base import ChunkedLLM
from services.llm_gemma import GemmaLLM
from services.llm_openai import OpenAILLM
from services.llm_qwen import QwenLLM

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

# ── 평가 기준 ───────────────────────────────────────────────────
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


def run_summarize(llm: ChunkedLLM, key: str, sample: dict) -> dict:
    section(f'[{key}] {sample["label"]}')
    text = sample['text']
    print(f'  입력 길이: {len(text)}자')

    t0 = time.perf_counter()
    result = llm.generate(text, TaskType.SUMMARIZE)
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


def run_qa(llm: ChunkedLLM, key: str, sample: dict) -> dict | None:
    question = sample.get('question')
    if not question:
        return None

    print(f'\n  ▶ QA: {question}')
    t0 = time.perf_counter()
    result = llm.generate(sample['text'], TaskType.QA, question=question)
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


ENGINE_DEFAULTS = {
    'gemma': 'google/gemma-4-E4B-it',
    'qwen': 'Qwen/Qwen2.5-7B-Instruct',
    'gpt': 'gpt-4.1-mini',
}

ALL_ENGINES = list(ENGINE_DEFAULTS.keys())


def build_llm(engine: str, model: str | None) -> ChunkedLLM:
    """엔진 이름에 따라 LLM 인스턴스를 생성한다."""
    model_name = model or ENGINE_DEFAULTS[engine]
    if engine == 'gemma':
        return GemmaLLM(model_name=model_name)
    if engine == 'gpt':
        return OpenAILLM(model_name=model_name)
    return QwenLLM(model_name=model_name)


def main() -> None:
    parser = argparse.ArgumentParser(description='LLM 실 추론 테스트')
    parser.add_argument(
        '--engine',
        choices=[*ALL_ENGINES, 'all'],
        default='gemma',
        help='사용할 엔진 (기본: gemma, all: 전체)',
    )
    with open(data_path() / 'sample_texts.json', encoding='utf-8') as f:
        samples_dict = json.loads(f.read())

    parser.add_argument(
        '--sample', choices=list(samples_dict.keys()), help='특정 샘플만 실행'
    )
    parser.add_argument('--qa', action='store_true', help='QA 테스트도 함께 실행')
    parser.add_argument('--model', default=None, help='엔진 기본값 대신 사용할 모델명')
    args = parser.parse_args()

    engines = ALL_ENGINES if args.engine == 'all' else [args.engine]
    targets = {args.sample: samples_dict[args.sample]} if args.sample else samples_dict

    print('\n🚀 LLM 실 테스트 시작')
    print(f'   엔진: {", ".join(engines)}')
    print(f'   모드: 요약{"+ QA" if args.qa else ""}')

    all_results: dict = {}
    for engine in engines:
        model_name = args.model or ENGINE_DEFAULTS[engine]
        print(f'\n{"═" * 55}')
        print(f'  엔진: {engine}  /  모델: {model_name}')

        t_load = time.perf_counter()
        llm = build_llm(engine, args.model)
        print(f'  준비 완료: {time.perf_counter() - t_load:.1f}s')

        for key, sample in targets.items():
            result_key = f'{engine}/{key}'
            all_results[result_key] = {}
            all_results[result_key]['summarize'] = run_summarize(llm, key, sample)
            if args.qa:
                qa_res = run_qa(llm, key, sample)
                if qa_res:
                    all_results[result_key]['qa'] = qa_res

    print_summary(all_results)


if __name__ == '__main__':
    main()
