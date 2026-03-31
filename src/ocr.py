"""OCR 모듈 — PaddleOCR (로컬) + ClovaOCR (API 폴백)."""

from __future__ import annotations

import numpy as np
from PIL import Image

from src.base import BaseOCR

# ── 로컬: PaddleOCR ──────────────────────────────────────────────────────────


class PaddleOCREngine(BaseOCR):
    """PaddleOCR 기반 로컬 OCR 엔진."""

    _instance = None  # 싱글톤

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._ocr = None
        return cls._instance

    def _get_ocr(self):
        if self._ocr is None:
            from paddleocr import PaddleOCR

            self._ocr = PaddleOCR(use_angle_cls=True, lang='korean', show_log=False)
        return self._ocr

    def extract(self, image: np.ndarray, confidence_threshold: float = 0.8) -> str:
        """PaddleOCR로 텍스트 추출, 저신뢰도 구간은 TrOCR 재인식."""
        ocr = self._get_ocr()
        results = ocr.ocr(image, cls=True)

        if not results or not results[0]:
            return ''

        lines: list[str] = []
        for line in results[0]:
            bbox, (text, conf) = line
            if conf >= confidence_threshold:
                lines.append(text)
            else:
                region = _crop_region(image, bbox)
                recovered = _trocr_recognize(region)
                lines.append(recovered if recovered else text)

        return _merge_lines(lines)


# ── API 폴백: Naver HyperCLOVA (HDX-005) ────────────────────────────────────


class ClovaOCR(BaseOCR):
    """네이버 클로바 HDX-005 기반 API OCR 엔진.

    입력 타입별 엔드포인트:
        이미지 파일 → /general
        PDF 파일    → /document (보류)
    """

    API_URL = 'https://naveropenapi.apigw.ntruss.com/vision/v1/ocr'

    def __init__(self, api_key: str):
        self._api_key = api_key

    def extract(self, image: np.ndarray) -> str:
        """Clova OCR API로 텍스트 추출."""
        import cv2
        import requests

        _, img_encoded = cv2.imencode('.jpg', image)
        response = requests.post(
            self.API_URL,
            headers={'X-NCP-APIGW-API-KEY': self._api_key},
            files={'image': ('image.jpg', img_encoded.tobytes(), 'image/jpeg')},
            data={'lang': 'ko', 'resultType': 'string'},
        )
        response.raise_for_status()
        return response.json().get('result', '')


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────


def _crop_region(image: np.ndarray, bbox: list) -> np.ndarray:
    """bbox 좌표로 이미지 영역 크롭."""
    import cv2

    pts = np.array(bbox, dtype=np.int32)
    x, y, w, h = cv2.boundingRect(pts)
    return image[y : y + h, x : x + w]


def _trocr_recognize(region: np.ndarray) -> str:
    """TrOCR로 단일 영역 텍스트 재인식."""
    try:
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel

        processor = TrOCRProcessor.from_pretrained('microsoft/trocr-base-printed')
        model = VisionEncoderDecoderModel.from_pretrained(
            'microsoft/trocr-base-printed'
        )
        pil_img = Image.fromarray(region).convert('RGB')
        pixel_values = processor(pil_img, return_tensors='pt').pixel_values
        generated_ids = model.generate(pixel_values)
        return processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
    except Exception:
        return ''


def _merge_lines(lines: list[str]) -> str:
    """파편화된 텍스트 라인을 문단으로 병합."""
    return ' '.join(line.strip() for line in lines if line.strip())
