"""
ReadMate LLM 수동 점검 스크립트.

예시:
    python scripts/run_llm_check.py
    python scripts/run_llm_check.py --engine gemma --sample science_climate --qa
    python scripts/run_llm_check.py --engine qwen --sample history_printing
    python scripts/run_llm_check.py --engine gpt --sample study_memory --qa
    python scripts/run_llm_check.py --list-samples
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.config import LLM_MODEL_API, LLM_MODEL_DEFAULT, OPENAI_API_KEY
from lib.utils.path import data_path
from models.schemas import LLMResult, TaskType
from services.llm_base import ChunkedLLM
from services.llm_gemma import GemmaLLM
from services.llm_openai import OpenAILLM
from services.llm_qwen import QwenLLM

ENGINE_DEFAULTS: dict[str, str] = {
    'gemma': LLM_MODEL_DEFAULT,
    'qwen': 'Qwen/Qwen2.5-7B-Instruct',
    'gpt': LLM_MODEL_API,
}


def load_samples() -> dict[str, dict[str, str]]:
    """
    샘플 텍스트 파일을 로드한다.

    Returns:
        dict[str, dict[str, str]]: 샘플 키와 본문 정보
    """
    sample_path = data_path() / 'sample_texts.json'
    with sample_path.open(encoding='utf-8') as file:
        return json.load(file)


def print_section(title: str) -> None:
    """
    콘솔 섹션 제목을 출력한다.

    Args:
        title: 출력할 제목
    """
    print(f'\n{"=" * 60}')
    print(title)
    print(f'{"=" * 60}')


def print_result(result: LLMResult, elapsed_sec: float) -> None:
    """
    LLM 결과를 보기 좋게 출력한다.

    Args:
        result: 요약 또는 QA 결과
        elapsed_sec: 실행 시간
    """
    print(f'엔진: {result.engine}')
    print(f'실행 시간: {elapsed_sec:.2f}s')
    print('\n[요약]')
    print(result.summary)

    print('\n[핵심 포인트]')
    for index, key_point in enumerate(result.key_points, start=1):
        print(f'{index}. {key_point}')

    if result.qa_answer:
        print('\n[답변]')
        print(result.qa_answer)


def build_llm(engine: str, model_name: str) -> ChunkedLLM:
    """
    선택한 엔진 이름에 따라 LLM 인스턴스를 생성한다.

    Args:
        engine: gemma | qwen | gpt
        model_name: 사용할 모델명

    Returns:
        ChunkedLLM: 실행 가능한 LLM 인스턴스
    """
    if engine == 'gemma':
        return GemmaLLM(model_name=model_name)
    if engine == 'qwen':
        return QwenLLM(model_name=model_name)
    if not OPENAI_API_KEY:
        raise ValueError('GPT 엔진 실행에는 OPENAI_API_KEY 설정이 필요합니다.')
    return OpenAILLM(model_name=model_name)


def run_sample(
    llm: ChunkedLLM,
    sample_key: str,
    sample: dict[str, str],
    run_qa: bool,
) -> None:
    """
    선택한 샘플에 대해 요약과 QA를 실행한다.

    Args:
        llm: 실행할 LLM 인스턴스
        sample_key: 샘플 식별자
        sample: 샘플 데이터
        run_qa: QA 실행 여부
    """
    label = sample['label']
    text = sample['text']
    question = sample.get('question')

    print_section(f'샘플: {sample_key} | {label}')
    print(f'본문 길이: {len(text)}자')

    started_at = time.perf_counter()
    summary_result = llm.generate(text, TaskType.SUMMARIZE)
    print_result(summary_result, time.perf_counter() - started_at)

    if run_qa and question:
        print_section('QA')
        print(f'질문: {question}')
        started_at = time.perf_counter()
        qa_result = llm.generate(text, TaskType.QA, question=question)
        print_result(qa_result, time.perf_counter() - started_at)


def build_parser(sample_keys: list[str]) -> argparse.ArgumentParser:
    """
    CLI 인자 파서를 생성한다.

    Args:
        sample_keys: 사용 가능한 샘플 키 목록

    Returns:
        argparse.ArgumentParser: 설정된 파서
    """
    parser = argparse.ArgumentParser(description='ReadMate LLM 수동 점검 스크립트')
    parser.add_argument(
        '--engine',
        choices=['gemma', 'qwen', 'gpt'],
        default='gemma',
        help='실행할 LLM 엔진',
    )
    parser.add_argument(
        '--sample',
        choices=sample_keys,
        default='science_climate',
        help='실행할 샘플 키',
    )
    parser.add_argument(
        '--qa',
        action='store_true',
        help='선택한 샘플의 질문까지 함께 실행',
    )
    parser.add_argument(
        '--list-samples',
        action='store_true',
        help='사용 가능한 샘플 목록만 출력',
    )
    parser.add_argument(
        '--model',
        default=None,
        help='엔진 기본값 대신 사용할 모델명',
    )
    return parser


def print_sample_list(samples: dict[str, dict[str, str]]) -> None:
    """
    사용 가능한 샘플 목록을 출력한다.

    Args:
        samples: 전체 샘플 데이터
    """
    print_section('사용 가능한 샘플')
    for key, sample in samples.items():
        print(f'- {key}: {sample["label"]}')


def main() -> None:
    """스크립트 진입점."""
    samples = load_samples()
    parser = build_parser(sorted(samples.keys()))
    args = parser.parse_args()

    if args.list_samples:
        print_sample_list(samples)
        return

    model_name = args.model or ENGINE_DEFAULTS[args.engine]

    print_section('LLM 점검 시작')
    print(f'엔진: {args.engine}')
    print(f'모델: {model_name}')
    print(f'샘플: {args.sample}')
    print(f'QA 실행: {args.qa}')

    llm = build_llm(args.engine, model_name)
    run_sample(llm, args.sample, samples[args.sample], args.qa)


if __name__ == '__main__':
    main()
