"""
OCR 서비스 테스트 스크립트.

테스트 케이스:
  1. PDF 페이지 텍스트 추출 (기존)
  2. 접근성 묘사: 표 / 해부도 / 일반 사진 (신규)

사용법:
    uv run python scripts/test_ocr.py
    uv run python scripts/test_ocr.py --pdf-only      # PDF 테스트만
    uv run python scripts/test_ocr.py --access-only   # 접근성 테스트만
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src'))

POPPLER_PATH = r'C:\Release-25.12.0-0\poppler-25.12.0\Library\bin'
PDF_PATH = ROOT / 'data' / '주제_문제제기 pt.pdf'

# 접근성 테스트용 이미지 경로 (data/test_images/ 에 준비)
TEST_IMAGES = {
    'table': ROOT / 'data' / 'test_images' / 'table.png',
    'anatomy': ROOT / 'data' / 'test_images' / 'anatomy.png',
    'photo': ROOT / 'data' / 'test_images' / 'photo.png',
}


def test_pdf() -> None:
    """기존 PDF 텍스트 추출 테스트."""
    from pdf2image import convert_from_bytes
    from services.ocr_service import Qwen2VLEngine

    print('=== PDF 텍스트 추출 테스트 ===\n')

    if not PDF_PATH.exists():
        print(f'[SKIP] PDF 파일 없음: {PDF_PATH}')
        return

    ocr = Qwen2VLEngine()

    with open(PDF_PATH, 'rb') as f:
        pdf_bytes = f.read()

    images = convert_from_bytes(pdf_bytes, dpi=200, poppler_path=POPPLER_PATH)

    for i, img in enumerate(images):
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        result = ocr.recognize(buf.getvalue())
        print(f'--- 페이지 {i + 1} ---')
        print(f'유형: {result.image_type.value}')
        print(f'엔진: {result.engine}')
        print(f'텍스트:\n{result.raw_text}\n')


def test_accessibility() -> None:
    """접근성 묘사 테스트 (표 / 해부도 / 일반 사진)."""
    from services.ocr_service import Qwen2VLEngine
    from models.schemas import ImageType

    print('=== 접근성 묘사 테스트 ===\n')

    ocr = Qwen2VLEngine()

    expected_types = {
        'table': ImageType.TABLE,
        'anatomy': ImageType.ANATOMY,
        'photo': ImageType.PHOTO,
    }

    for name, path in TEST_IMAGES.items():
        if not path.exists():
            print(f'[SKIP] 이미지 없음: {path}')
            print(f'       → data/test_images/{name}.png 를 준비해주세요.\n')
            continue

        print(f'--- {name} ---')
        image_bytes = path.read_bytes()
        result = ocr.recognize(image_bytes)

        expected = expected_types[name]
        status = '✓' if result.image_type == expected else f'✗ (예상: {expected.value})'
        print(f'유형 분류: {result.image_type.value} {status}')
        print(f'묘사 텍스트:\n{result.alt_text}\n')


def main() -> None:
    args = sys.argv[1:]
    pdf_only = '--pdf-only' in args
    access_only = '--access-only' in args

    if not pdf_only:
        test_accessibility()
    if not access_only:
        test_pdf()


if __name__ == '__main__':
    main()
