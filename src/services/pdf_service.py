"""
PDF 텍스트 추출 엔진 구현.

텍스트형 PDF:
  - PyMuPDF(fitz)로 텍스트 블록 추출
  - find_tables()로 표를 JSON 구조로 추출 → 선형화 텍스트 변환
  - 텍스트와 선형화된 표를 페이지 내 Y좌표 순서대로 합치기

이미지형 PDF (스캔본):
  - pdf2image로 페이지 전체를 이미지로 변환
  - Qwen2.5-VL 통합 프롬프트로 텍스트 + 표 선형화 처리
"""

import io
import logging
from typing import TYPE_CHECKING

import fitz  # PyMuPDF
import pypdf

from core.config import POPPLER_PATH
from models.schemas import PDFResult
from services.base import BasePDF

if TYPE_CHECKING:
    from services.ocr_service import Qwen2VLEngine

logger = logging.getLogger(__name__)

_SCAN_THRESHOLD_TOTAL = 100
_SCAN_THRESHOLD_PER_PAGE = 50

# 페이지 전체 통합 처리 프롬프트
_PAGE_INTEGRATED_PROMPT = """이 페이지에 있는 모든 내용을 위에서 아래 순서대로 출력하세요.

규칙 1 — 일반 텍스트: 제목, 본문, 캡션을 그대로 출력. 생략 금지.

규칙 2 — 표: 아래 형식으로 각 행을 선형화. | 기호 절대 금지.
출력 형식: (열 제목): (내용). (열 제목): (내용).
예시 출력:
경맥명: 수태음폐경. 경혈명: 중부. 부위: 빗장뼈 아래, 앞정중선에서 가쪽으로 6촌. 효능: 기침, 천식, 가슴 통증.
경맥명: 수태음폐경. 경혈명: 척택. 부위: 팔오금주름 위, 위팔두갈래근힘줄의 가쪽. 효능: 목구멍 통증, 팔 통증.

규칙 3 — 그림/이미지: 건너뛰세요. 설명하지 마세요.

금지: 마크다운 헤더(#), 마크다운 테이블(|), 내용 생략"""


class PyPDFEngine(BasePDF):
    """
    pypdf + PyMuPDF 기반 PDF 텍스트 추출 엔진.
    텍스트형: 텍스트 블록 + 표 선형화 (Y좌표 순서 유지).
    스캔형: 페이지 전체 이미지 → Qwen2.5-VL OCR 처리.
    """

    def __init__(self, ocr_fallback: 'Qwen2VLEngine') -> None:
        """
        Args:
            ocr_fallback: OCR 엔진 (Qwen2VLEngine)
        """
        self._ocr = ocr_fallback

    def extract(self, pdf_bytes: bytes) -> PDFResult:
        """
        PDF 바이트를 받아 텍스트 + 표 선형화 추출.

        Args:
            pdf_bytes: PDF 원본 바이트

        Returns:
            PDFResult: 추출 텍스트, 페이지 수, 스캔형 여부
        """
        try:
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            page_count = len(reader.pages)
            logger.info('PDF 파싱 완료: pages=%d', page_count)
        except Exception as e:
            raise RuntimeError(f'PDF 파싱 실패: {e}') from e

        pages_text = self._extract_text_pages(reader)
        is_scanned = self._is_scanned(pages_text)

        if is_scanned:
            logger.info('스캔형 PDF → 페이지 이미지 렌더링 후 OCR 처리')
            text = self._ocr_pdf_integrated(pdf_bytes)
        else:
            logger.info('텍스트형 PDF → pypdf 텍스트 추출')
            text = self._extract_text(pdf_bytes, pages_text)

        return PDFResult(text=text, page_count=page_count, is_scanned=is_scanned)

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
        is_scan = total_len < _SCAN_THRESHOLD_TOTAL or avg_len < _SCAN_THRESHOLD_PER_PAGE
        logger.info(
            '스캔형 판별: total=%d, avg=%.1f, is_scanned=%s',
            total_len, avg_len, is_scan,
        )
        return is_scan

    def _extract_text(self, pdf_bytes: bytes, pages_text: list[str]) -> str:
        """
        텍스트형 PDF 처리.
        PyMuPDF로 텍스트 블록 + find_tables()로 표를 추출.
        표는 JSON 구조로 파싱 후 선형화 텍스트로 변환.
        텍스트 블록과 선형화된 표를 Y좌표 순서로 합산.

        Args:
            pdf_bytes: PDF 원본 바이트
            pages_text: pypdf로 추출한 페이지별 텍스트 리스트

        Returns:
            전체 페이지 텍스트 (표는 선형화됨)
        """
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        all_pages: list[str] = []

        for page_idx, page in enumerate(doc):
            page_blocks: list[tuple[float, str]] = []  # (y좌표, 텍스트)

            # 표 추출 및 영역 수집
            tables = page.find_tables()
            table_rects: list[fitz.Rect] = []
            for tab in tables:
                table_rects.append(fitz.Rect(tab.bbox))
                linearized = self._linearize_table(tab)
                if linearized:
                    y0 = tab.bbox[1]
                    page_blocks.append((y0, linearized))
                    logger.info(
                        '페이지 %d 표 추출: %d행 x %d열',
                        page_idx + 1, tab.row_count, tab.col_count,
                    )

            # 텍스트 블록 수집 (표 영역과 겹치는 블록은 제외)
            blocks = page.get_text('blocks')  # (x0, y0, x1, y1, text, block_no, block_type)
            for block in blocks:
                block_text = block[4].strip()
                if not block_text:
                    continue
                block_rect = fitz.Rect(block[:4])
                if any(block_rect.intersects(tr) for tr in table_rects):
                    continue  # 표 영역 내부 텍스트는 건너뜀
                page_blocks.append((block[1], block_text))

            # Y좌표 기준 정렬 후 텍스트 합치기
            page_blocks.sort(key=lambda x: x[0])
            page_text = '\n\n'.join(text for _, text in page_blocks)

            if not page_text.strip():
                page_text = pages_text[page_idx]

            all_pages.append(page_text)
            logger.info('페이지 %d 처리 완료: 블록=%d', page_idx + 1, len(page_blocks))

        doc.close()
        return '\n\n'.join(all_pages)

    @staticmethod
    def _linearize_table(tab: fitz.table.Table) -> str:
        """
        PyMuPDF 테이블을 시각장애인 친화 선형화 텍스트로 변환.
        각 행을 '(열 제목): (내용)' 형태로 풀어서 서술.

        Args:
            tab: PyMuPDF find_tables() 결과 테이블 객체

        Returns:
            선형화된 텍스트 (행마다 줄바꿈 구분)
        """
        headers = [
            (c or '').replace('\n', ' ').strip() for c in tab.header.names
        ]
        rows = tab.extract()
        # 첫 행이 헤더와 동일하면 건너뜀
        data_start = 1 if rows and rows[0] == list(tab.header.names) else 0

        lines: list[str] = []
        for row in rows[data_start:]:
            cells = [(c or '').replace('\n', ' ').strip() for c in row]
            parts = [f'{h}: {v}' for h, v in zip(headers, cells) if v]
            if parts:
                lines.append('. '.join(parts) + '.')
        return '\n'.join(lines)

    def _ocr_pdf_integrated(self, pdf_bytes: bytes) -> str:
        """
        스캔형 PDF: 각 페이지를 이미지로 변환 후
        통합 프롬프트로 Qwen2.5-VL에 처리.
        텍스트 + 이미지 묘사를 한 번에 생성.
        """
        try:
            from pdf2image import convert_from_bytes
        except ImportError as e:
            raise RuntimeError(
                'pdf2image 라이브러리 미설치. uv add pdf2image 및 Poppler 바이너리 설치 필요'
            ) from e

        try:
            images = convert_from_bytes(pdf_bytes, dpi=200, poppler_path=POPPLER_PATH or None)
        except Exception as e:
            raise RuntimeError(f'PDF 페이지 렌더링 실패: {e}') from e

        parts: list[str] = []
        for i, pil_img in enumerate(images):
            try:
                # 페이지마다 개별 호출 — 토큰을 온전히 사용
                page_text = self._ocr.recognize_pil(
                    pil_img, _PAGE_INTEGRATED_PROMPT, max_new_tokens=4096
                )
                logger.info('페이지 %d 처리 완료: 길이=%d', i + 1, len(page_text))
            except Exception as e:
                logger.warning('페이지 %d 처리 실패: %s', i + 1, e)
                page_text = ''

            parts.append(f'--- 페이지 {i + 1} ---\n\n{page_text}')

        result = '\n\n'.join(parts)
        logger.info('PDF 완료: pages=%d, total_length=%d', len(images), len(result))
        return result
