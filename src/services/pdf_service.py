"""
ReadMate PDF 추출 서비스.
- PyPDFEngine: pypdf로 텍스트 추출, 스캔형이면 OCR로 내부 분기
"""

from __future__ import annotations

import io
import logging

from pypdf import PdfReader

try:
    from pdf2image import convert_from_bytes

    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

from core.config import PDF_MIN_CHARS
from core.exceptions import PDFExtractionError
from models.schemas import PDFResult
from services.base import BaseOCR, BasePDF

logger = logging.getLogger(__name__)


class PyPDFEngine(BasePDF):
    """
    pypdf 기반 PDF 추출 엔진.
    텍스트 추출량이 PDF_MIN_CHARS 미만이면 스캔형으로 판별하고
    ocr_fallback 엔진으로 페이지별 이미지 OCR을 수행한다.
    """

    def __init__(self, ocr_fallback: BaseOCR) -> None:
        """
        PyPDF 엔진을 초기화한다.

        Args:
            ocr_fallback: 스캔형 PDF 처리용 OCR 엔진
        """
        self.ocr_fallback = ocr_fallback

    def extract(self, pdf_bytes: bytes) -> PDFResult:
        """
        PDF 바이트에서 텍스트를 추출한다.
        텍스트가 부족하면 스캔형으로 판별 후 OCR로 분기한다.

        Args:
            pdf_bytes: PDF 원본 바이트

        Returns:
            PDFResult: 추출 텍스트, 페이지 수, 스캔형 여부

        Raises:
            PDFExtractionError: pypdf 파싱 실패 시
        """
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
        except Exception as exc:
            raise PDFExtractionError(f'PDF 파싱 실패: {exc}') from exc

        page_count = len(reader.pages)
        text = self._extract_text(reader)

        logger.info('[pdf:pypdf] pages=%d chars=%d', page_count, len(text))

        if len(text.strip()) < PDF_MIN_CHARS:
            logger.info('[pdf] 스캔형 판별 → OCR 분기')
            text = self._ocr_all_pages(pdf_bytes, page_count)
            return PDFResult(text=text, page_count=page_count, is_scanned=True)

        return PDFResult(text=text, page_count=page_count, is_scanned=False)

    @staticmethod
    def _extract_text(reader: PdfReader) -> str:
        """
        모든 페이지에서 텍스트를 추출해 합친다.

        Args:
            reader: PdfReader 인스턴스

        Returns:
            str: 전체 페이지 텍스트 (페이지 구분자 포함)
        """
        parts: list[str] = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text() or ''
            if page_text.strip():
                parts.append(f'[페이지 {i + 1}]\n{page_text.strip()}')
        return '\n\n'.join(parts)

    def _ocr_all_pages(self, pdf_bytes: bytes, page_count: int) -> str:
        """
        스캔형 PDF의 각 페이지를 이미지로 변환 후 OCR 처리한다.
        pdf2image를 사용하며, 없을 경우 빈 텍스트를 반환한다.

        Args:
            pdf_bytes: PDF 원본 바이트
            page_count: 총 페이지 수

        Returns:
            str: 전체 페이지 OCR 결과 텍스트
        """
        if not PDF2IMAGE_AVAILABLE:
            logger.warning('[pdf] pdf2image 미설치 → 스캔형 OCR 불가')
            return ''

        try:
            images = convert_from_bytes(pdf_bytes, dpi=200)
        except Exception as exc:
            logger.error('[pdf] PDF → 이미지 변환 실패: %s', exc)
            return ''

        parts: list[str] = []
        for i, image in enumerate(images):
            img_bytes = self._pil_to_bytes(image)
            ocr_result = self.ocr_fallback.recognize(img_bytes)
            if ocr_result.raw_text.strip():
                parts.append(f'[페이지 {i + 1}]\n{ocr_result.raw_text.strip()}')
            logger.info(
                '[pdf:ocr] page=%d/%d chars=%d',
                i + 1,
                len(images),
                len(ocr_result.raw_text),
            )

        return '\n\n'.join(parts)

    @staticmethod
    def _pil_to_bytes(image) -> bytes:
        """PIL Image → JPEG 바이트 변환."""
        buf = io.BytesIO()
        image.convert('RGB').save(buf, format='JPEG', quality=95)
        return buf.getvalue()
