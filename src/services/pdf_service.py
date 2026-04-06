"""
PDF 텍스트 추출 엔진 구현.
텍스트형 PDF는 pypdf로 추출, 스캔형은 Qwen2.5-VL OCR로 처리.
"""

import io
import logging

import pypdf

from models.schemas import PDFResult
from services.base import BaseOCR, BasePDF

logger = logging.getLogger(__name__)

_SCAN_THRESHOLD_TOTAL = 100  # 전체 텍스트가 이 미만이면 스캔형
_SCAN_THRESHOLD_PER_PAGE = 50  # 페이지 평균이 이 미만이면 스캔형


class PyPDFEngine(BasePDF):
    """
    pypdf 기반 PDF 텍스트 추출 엔진.
    스캔형 판별 후 PaddleOCR 폴백 처리.
    """

    def __init__(self, ocr_fallback: BaseOCR) -> None:
        """
        Args:
            ocr_fallback: 스캔형 PDF 처리에 사용할 OCR 엔진
        """
        self._ocr = ocr_fallback

    def extract(self, pdf_bytes: bytes) -> PDFResult:
        """
        PDF 바이트를 받아 텍스트 추출.

        1단계: pypdf로 텍스트 추출 시도
        2단계: 스캔형이면 페이지를 이미지로 변환 후 PaddleOCR 적용

        Args:
            pdf_bytes: PDF 원본 바이트

        Returns:
            PDFResult: 추출 텍스트, 페이지 수, 스캔형 여부

        Raises:
            RuntimeError: PDF 파싱 실패 시
        """
        try:
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            page_count = len(reader.pages)
            logger.info('PDF 파싱 완료: pages=%d', page_count)
        except Exception as e:
            raise RuntimeError(f'PDF 파싱 실패: {e}') from e

        pages_text = self._extract_text_pages(reader)

        if self._is_scanned(pages_text):
            logger.info('스캔형 PDF 감지, OCR 처리 시작')
            text = self._ocr_pdf(pdf_bytes)
            return PDFResult(text=text, page_count=page_count, is_scanned=True)

        text = '\n\n'.join(pages_text)
        logger.info('텍스트형 PDF 추출: length=%d', len(text))
        return PDFResult(text=text, page_count=page_count, is_scanned=False)

    def _extract_text_pages(self, reader: pypdf.PdfReader) -> list[str]:
        """각 페이지에서 텍스트를 추출해 리스트로 반환."""
        pages_text = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ''
            pages_text.append(text)
            if i == 0:
                logger.debug('첫 페이지 샘플: %s...', text[:100])
        return pages_text

    def _is_scanned(self, pages_text: list[str]) -> bool:
        """
        텍스트 길이 기준으로 스캔형 여부 판별.
        전체 텍스트 < 100자 또는 페이지 평균 < 50자이면 스캔형.
        """
        total_len = sum(len(t) for t in pages_text)
        avg_len = total_len / len(pages_text) if pages_text else 0

        is_scan = (
            total_len < _SCAN_THRESHOLD_TOTAL or avg_len < _SCAN_THRESHOLD_PER_PAGE
        )
        logger.info(
            '스캔형 판별: total=%d, avg=%.1f, is_scanned=%s',
            total_len,
            avg_len,
            is_scan,
        )
        return is_scan

    def _ocr_pdf(self, pdf_bytes: bytes) -> str:
        """
        스캔형 PDF 각 페이지를 이미지로 변환 후 OCR 수행.
        pdf2image로 페이지를 렌더링, PIL 이미지 → bytes → OCR 처리.
        """
        try:
            from pdf2image import convert_from_bytes
        except ImportError as e:
            raise RuntimeError(
                'pdf2image 라이브러리 미설치. '
                'uv add pdf2image 및 Poppler 바이너리 설치 필요'
            ) from e

        try:
            images = convert_from_bytes(pdf_bytes, dpi=200)
        except Exception as e:
            logger.warning('pdf2image 변환 실패: %s, 직접 OCR 불가', e)
            raise RuntimeError(f'PDF 페이지 렌더링 실패: {e}') from e

        texts = []
        for i, pil_img in enumerate(images):
            # PIL 이미지 → PNG bytes
            buf = io.BytesIO()
            pil_img.save(buf, format='PNG')
            buf.seek(0)

            # OCR 처리
            try:
                ocr_result = self._ocr.recognize(buf.getvalue())
                texts.append(ocr_result.raw_text)
                logger.debug(
                    'OCR 페이지 %d: confidence=%.3f, text_len=%d',
                    i,
                    ocr_result.avg_confidence,
                    len(ocr_result.raw_text),
                )
            except Exception as e:
                logger.warning('페이지 %d OCR 실패: %s, 빈 문자열로 대체', i, e)
                texts.append('')

        result = '\n\n'.join(texts)
        logger.info('OCR PDF 완료: pages=%d, total_length=%d', len(images), len(result))
        return result
