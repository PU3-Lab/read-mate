"""
ReadMate OCR 서비스 구현체.
- PaddleOCREngine: 로컬 기본 엔진
- ClovaOCREngine:  HDX-005 API 폴백 엔진
"""

from __future__ import annotations

import io
import json
import logging
import uuid
from pathlib import Path

import numpy as np
import requests
from PIL import Image

from core.config import (
    CLOVA_API_KEY,
    CLOVA_API_URL,
    OCR_CONFIDENCE_THRESHOLD,
    TMP_DIR,
)
from core.exceptions import OCRQualityError
from lib.utils.device import available_device
from models.schemas import OCRBox, OCRResult
from services.base import BaseOCR

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────
# PaddleOCR 로컬 엔진
# ─────────────────────────────────────────


class PaddleOCREngine(BaseOCR):
    """PaddleOCR 기반 로컬 OCR 엔진 (싱글톤 모델)."""

    _instance: PaddleOCREngine | None = None
    _ocr = None

    def __new__(cls) -> PaddleOCREngine:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._ocr is not None:
            return
        from paddleocr import PaddleOCR

        device = available_device()
        use_gpu = device == 'cuda'
        logger.info('[ocr] PaddleOCR loading use_gpu=%s', use_gpu)
        self._ocr = PaddleOCR(
            use_angle_cls=True,
            lang='korean',
            use_gpu=use_gpu,
            show_log=False,
        )

    def recognize(self, image_bytes: bytes) -> OCRResult:
        """
        이미지 바이트를 PaddleOCR로 인식한다.

        Args:
            image_bytes: 이미지 원본 바이트

        Returns:
            OCRResult: 박스 목록, 평균 confidence, 원문 텍스트
        """
        image_array = self._bytes_to_array(image_bytes)
        raw = self._ocr.ocr(image_array, cls=True)

        boxes: list[OCRBox] = []
        for page in raw or []:
            for line in page or []:
                bbox, (text, conf) = line
                boxes.append(
                    OCRBox(
                        text=text,
                        confidence=float(conf),
                        bbox=[[int(p[0]), int(p[1])] for p in bbox],
                        source='paddle',
                    )
                )

        avg_conf = sum(b.confidence for b in boxes) / len(boxes) if boxes else 0.0
        raw_text = '\n'.join(b.text for b in boxes)

        logger.info('[ocr:paddle] boxes=%d avg_conf=%.2f', len(boxes), avg_conf)

        if avg_conf < OCR_CONFIDENCE_THRESHOLD and boxes:
            logger.warning('[ocr:paddle] 품질 낮음 avg_conf=%.2f', avg_conf)

        return OCRResult(
            boxes=boxes,
            engine='paddle',
            avg_confidence=avg_conf,
            raw_text=raw_text,
        )

    @staticmethod
    def _bytes_to_array(image_bytes: bytes) -> np.ndarray:
        """이미지 바이트 → numpy array (RGB)."""
        image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        return np.array(image)


# ─────────────────────────────────────────
# Clova OCR API 폴백 엔진
# ─────────────────────────────────────────


class ClovaOCREngine(BaseOCR):
    """네이버 Clova OCR HDX-005 API 폴백 엔진."""

    def __init__(
        self,
        api_key: str = CLOVA_API_KEY,
        api_url: str = CLOVA_API_URL,
    ) -> None:
        """
        ClovaOCR 엔진을 초기화한다.

        Args:
            api_key: Clova OCR API 키
            api_url: Clova OCR API 엔드포인트 URL
        """
        if not api_key or not api_url:
            raise ValueError(
                'CLOVA_API_KEY, CLOVA_API_URL이 .env에 설정되어 있지 않습니다.'
            )
        self.api_key = api_key
        self.api_url = api_url

    def recognize(self, image_bytes: bytes) -> OCRResult:
        """
        이미지 바이트를 Clova OCR API로 인식한다.

        Args:
            image_bytes: 이미지 원본 바이트

        Returns:
            OCRResult: 박스 목록, 평균 confidence, 원문 텍스트

        Raises:
            OCRQualityError: API 호출 실패 또는 응답 파싱 오류
        """
        # 임시 파일로 저장 후 multipart 업로드
        tmp_path = TMP_DIR / f'{uuid.uuid4().hex}.jpg'
        try:
            tmp_path.write_bytes(image_bytes)
            boxes = self._call_api(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        avg_conf = sum(b.confidence for b in boxes) / len(boxes) if boxes else 0.0
        raw_text = '\n'.join(b.text for b in boxes)

        logger.info('[ocr:clova] boxes=%d avg_conf=%.2f', len(boxes), avg_conf)
        return OCRResult(
            boxes=boxes,
            engine='clova',
            avg_confidence=avg_conf,
            raw_text=raw_text,
        )

    def _call_api(self, image_path: Path) -> list[OCRBox]:
        """
        Clova OCR API를 호출하고 결과를 파싱한다.

        Args:
            image_path: 임시 이미지 파일 경로

        Returns:
            list[OCRBox]: 인식된 텍스트 박스 목록

        Raises:
            OCRQualityError: HTTP 오류 또는 파싱 실패
        """
        request_body = {
            'images': [{'format': 'jpg', 'name': 'readmate'}],
            'requestId': uuid.uuid4().hex,
            'version': 'V2',
            'timestamp': 0,
        }
        try:
            with open(image_path, 'rb') as f:
                response = requests.post(
                    self.api_url,
                    headers={'X-OCR-SECRET': self.api_key},
                    data={'message': json.dumps(request_body)},
                    files={'file': f},
                    timeout=30,
                )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise OCRQualityError(f'Clova OCR API 호출 실패: {exc}') from exc

        boxes: list[OCRBox] = []
        for image_result in data.get('images', []):
            for field in image_result.get('fields', []):
                text = field.get('inferText', '').strip()
                conf = float(field.get('inferConfidence', 1.0))
                bounding_poly = field.get('boundingPoly', {})
                vertices = bounding_poly.get('vertices', [])
                bbox = [[int(v.get('x', 0)), int(v.get('y', 0))] for v in vertices]
                if text:
                    boxes.append(
                        OCRBox(text=text, confidence=conf, bbox=bbox, source='clova')
                    )

        return boxes
