"""
PDF 텍스트 추출 엔진 구현.

텍스트형 PDF:
  - pypdf로 텍스트 추출
  - PyMuPDF(fitz)로 페이지 내 내장 이미지 추출 → 접근성 묘사 생성
  - 텍스트와 이미지 설명을 페이지 내 순서대로 합치기

이미지형 PDF (스캔본):
  - pdf2image로 페이지 전체를 이미지로 변환
  - Qwen2.5-VL 통합 프롬프트로 텍스트 + 이미지 묘사 한 번에 처리
"""

import io
import logging
from typing import TYPE_CHECKING

import fitz  # PyMuPDF
import pypdf

from models.schemas import ImageType, PDFResult
from services.base import BasePDF

if TYPE_CHECKING:
    from services.ocr_service import Qwen2VLEngine

logger = logging.getLogger(__name__)

_SCAN_THRESHOLD_TOTAL = 100
_SCAN_THRESHOLD_PER_PAGE = 50

# 스캔형 PDF 전용: 페이지 전체 통합 처리 프롬프트
_PAGE_INTEGRATED_PROMPT = """당신은 시각장애인 학습자를 위한 교재 해설사입니다.
이 페이지 이미지를 분석해서 다음 규칙에 따라 처리하세요.

1. 텍스트가 있으면 그대로 추출
2. 그림/이미지가 있으면 아래 중 해당하는 방식으로 설명:
   - 표(행과 열 구조): 각 행을 "(열 제목): (내용)" 형태로 줄바꿈하며 선형화
   - 해부도/경혈도/근육도: "그림 설명 시작." ~ "그림 설명 끝." 형식으로,
     신체 기준 위치(자신의 왼쪽, 머리 방향 등)와 촉각 실습 안내 포함
   - 일반 그림/사진: "그림 설명 시작." ~ "그림 설명 끝." 형식으로 장면 묘사
3. 텍스트와 그림 설명은 페이지에 나타나는 순서대로 출력
4. 괄호·특수기호 최소화 (화면낭독기 친화적)"""


class PyPDFEngine(BasePDF):
    """
    pypdf + PyMuPDF 기반 PDF 텍스트 추출 엔진.
    텍스트형: 텍스트 추출 + 내장 이미지 접근성 묘사 (위치 순서 유지).
    스캔형: 페이지 전체 이미지 → 통합 프롬프트로 Qwen2.5-VL 처리.
    """

    def __init__(self, ocr_fallback: 'Qwen2VLEngine') -> None:
        """
        Args:
            ocr_fallback: OCR 엔진 (Qwen2VLEngine)
        """
        self._ocr = ocr_fallback

    def extract(self, pdf_bytes: bytes) -> PDFResult:
        """
        PDF 바이트를 받아 텍스트 + 이미지 묘사 추출.

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

        if self._is_scanned(pages_text):
            logger.info('스캔형 PDF 감지 → 페이지 통합 OCR 처리')
            text = self._ocr_pdf_integrated(pdf_bytes)
            return PDFResult(text=text, page_count=page_count, is_scanned=True)

        logger.info('텍스트형 PDF → 텍스트 + 내장 이미지 접근성 처리')
        text = self._extract_text_with_images(pdf_bytes, pages_text)
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
        is_scan = total_len < _SCAN_THRESHOLD_TOTAL or avg_len < _SCAN_THRESHOLD_PER_PAGE
        logger.info(
            '스캔형 판별: total=%d, avg=%.1f, is_scanned=%s',
            total_len, avg_len, is_scan,
        )
        return is_scan

    def _extract_text_with_images(self, pdf_bytes: bytes, pages_text: list[str]) -> str:
        """
        텍스트형 PDF 처리.
        PyMuPDF로 각 페이지의 내장 이미지를 추출하고,
        텍스트 블록과 이미지 묘사를 페이지 내 Y좌표 순서로 합쳐서 반환.

        Args:
            pdf_bytes: PDF 원본 바이트
            pages_text: pypdf로 추출한 페이지별 텍스트 리스트

        Returns:
            전체 페이지 텍스트 + 이미지 묘사 (순서 유지)
        """
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        all_pages: list[str] = []

        for page_idx, page in enumerate(doc):
            page_blocks: list[tuple[float, str]] = []  # (y좌표, 텍스트)

            # 텍스트 블록 수집 (Y좌표 포함)
            blocks = page.get_text('blocks')  # (x0, y0, x1, y1, text, block_no, block_type)
            for block in blocks:
                block_text = block[4].strip()
                if block_text:
                    y0 = block[1]
                    page_blocks.append((y0, block_text))

            # 내장 이미지 수집
            image_list = page.get_images(full=True)
            for img_info in image_list:
                xref = img_info[0]
                try:
                    img_bytes = self._extract_image_bytes(doc, xref)
                    if img_bytes is None:
                        continue

                    # 이미지 Y좌표: 페이지 내 이미지 위치 파악
                    y_pos = self._get_image_y_position(page, xref)

                    # 접근성 묘사 생성
                    ocr_result = self._ocr.recognize(img_bytes)
                    if ocr_result.image_type == ImageType.TEXT:
                        # 이미지 안이 텍스트만 있는 경우 그대로 사용
                        description = ocr_result.raw_text
                    else:
                        description = ocr_result.alt_text or ocr_result.raw_text

                    if description:
                        page_blocks.append((y_pos, description))

                    logger.info(
                        '페이지 %d 이미지 처리: xref=%d, type=%s',
                        page_idx + 1, xref, ocr_result.image_type.value,
                    )
                except Exception as e:
                    logger.warning('페이지 %d 이미지 처리 실패 (xref=%d): %s', page_idx + 1, xref, e)

            # Y좌표 기준 정렬 후 텍스트 합치기
            page_blocks.sort(key=lambda x: x[0])
            page_text = '\n\n'.join(text for _, text in page_blocks)

            if not page_text.strip():
                # PyMuPDF 블록 추출 실패 시 pypdf 결과로 폴백
                page_text = pages_text[page_idx]

            all_pages.append(page_text)
            logger.info('페이지 %d 처리 완료: 블록=%d', page_idx + 1, len(page_blocks))

        doc.close()
        return '\n\n'.join(all_pages)

    def _extract_image_bytes(self, doc: fitz.Document, xref: int) -> bytes | None:
        """
        PyMuPDF xref로 이미지 바이트 추출.
        PNG로 변환해서 반환. 실패 시 None.
        """
        try:
            base_image = doc.extract_image(xref)
            img_bytes = base_image['image']
            img_ext = base_image['ext']

            # PNG가 아니면 PIL로 변환
            if img_ext.lower() != 'png':
                from PIL import Image
                pil_img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
                buf = io.BytesIO()
                pil_img.save(buf, format='PNG')
                return buf.getvalue()

            return img_bytes
        except Exception as e:
            logger.warning('이미지 바이트 추출 실패 (xref=%d): %s', xref, e)
            return None

    def _get_image_y_position(self, page: fitz.Page, xref: int) -> float:
        """
        페이지 내 이미지의 Y좌표 반환.
        이미지를 찾지 못하면 페이지 높이(맨 아래)로 폴백.
        """
        for item in page.get_image_info():
            if item.get('xref') == xref:
                return item['bbox'][1]  # y0
        return page.rect.height  # 폴백: 페이지 맨 아래

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
            images = convert_from_bytes(pdf_bytes, dpi=200)
        except Exception as e:
            raise RuntimeError(f'PDF 페이지 렌더링 실패: {e}') from e

        texts: list[str] = []
        for i, pil_img in enumerate(images):
            try:
                # 통합 프롬프트: 분류 없이 텍스트+이미지 한 번에 처리
                page_text = self._ocr.recognize_pil(
                    pil_img, _PAGE_INTEGRATED_PROMPT, max_new_tokens=2048
                )
                texts.append(page_text)
                logger.info('스캔형 페이지 %d 처리 완료: 길이=%d', i + 1, len(page_text))
            except Exception as e:
                logger.warning('페이지 %d 처리 실패: %s', i + 1, e)
                texts.append('')

        result = '\n\n'.join(texts)
        logger.info('스캔형 PDF 완료: pages=%d, total_length=%d', len(images), len(result))
        return result
