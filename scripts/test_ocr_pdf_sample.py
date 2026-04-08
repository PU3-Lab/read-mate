"""
표 및 이미지 변환 테스트 — PyPDFEngine 전체 파이프라인 테스트.

대상: data/표_및_이미지_변환_테스트_샘플.pdf
  - 텍스트형 PDF: 텍스트 블록 + 내장 이미지 접근성 묘사를 Y좌표 순서로 합산

사용법:
    uv run python scripts/test_ocr_pdf_sample.py
"""

from __future__ import annotations

import datetime
import os
import sys
import time
from pathlib import Path

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding='utf-8')  # type: ignore[attr-defined]

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src'))

PDF_PATH = ROOT / 'data' / '표_및_이미지_변환_테스트_샘플.pdf'


def log(msg: str = '') -> None:
    """flush 보장 출력."""
    print(msg, flush=True)


def main() -> None:
    from services.ocr_service import Qwen2VLEngine
    from services.pdf_service import PyPDFEngine

    if not PDF_PATH.exists():
        log(f'[ERROR] PDF 파일 없음: {PDF_PATH}')
        return

    log(f'PDF: {PDF_PATH.name}')

    ocr = Qwen2VLEngine()
    pdf = PyPDFEngine(ocr_fallback=ocr)
    log('[모델 로드 완료]')

    with open(PDF_PATH, 'rb') as f:
        pdf_bytes = f.read()

    log('[추출 시작...]')
    t0 = time.perf_counter()
    result = pdf.extract(pdf_bytes)
    elapsed = time.perf_counter() - t0

    log(f'페이지 수: {result.page_count}')
    log(f'스캔형: {result.is_scanned}')
    log(f'소요 시간: {elapsed:.1f}s')
    log()
    log(result.text)

    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    out_dir = ROOT / 'data' / 'ocr_results'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f'{PDF_PATH.stem}_full_{timestamp}.txt'
    out_path.write_text(result.text, encoding='utf-8')
    log(f'\n[결과 저장] {out_path}')


if __name__ == '__main__':
    main()
