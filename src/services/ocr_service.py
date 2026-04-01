"""
PaddleOCR 기반 OCR 엔진 구현.
한글 문서 인식에 최적화, 싱글톤 패턴으로 모델 재로드 방지.
"""

import logging
from threading import Lock

import cv2
import numpy as np
from paddleocr import PaddleOCR

from src.lib.utils.device import available_device
from src.models.schemas import OCRBox, OCRResult
from src.services.base import BaseOCR

logger = logging.getLogger(__name__)


class PaddleOCREngine(BaseOCR):
  """
  PaddleOCR 기반 한글 문서 인식 엔진.
  싱글톤 패턴으로 모델을 한 번만 로드해 메모리 효율성 확보.
  """

  _instance: 'PaddleOCREngine | None' = None
  _lock: Lock = Lock()
  _ocr: PaddleOCR | None = None

  def __new__(cls) -> 'PaddleOCREngine':
    """싱글톤 인스턴스 반환."""
    with cls._lock:
      if cls._instance is None:
        cls._instance = super().__new__(cls)
        cls._instance._init_model()
    return cls._instance

  def _init_model(self) -> None:
    """
    PaddleOCR 모델 초기화.
    available_device()로 CUDA/CPU 사용 여부 결정.
    MPS는 PaddleOCR에서 미지원이므로 False로 처리.
    """
    device = available_device()
    use_gpu = device == 'cuda'  # paddle은 CUDA만 GPU 가속 지원

    logger.info('PaddleOCR 초기화: device=%s, use_gpu=%s', device, use_gpu)
    self._ocr = PaddleOCR(
        use_angle_cls=True,
        lang='korean',
        use_gpu=use_gpu,
        show_log=False,
    )

  def recognize(self, image_bytes: bytes) -> OCRResult:
    """
    이미지 바이트를 받아 PaddleOCR로 텍스트 인식.

    Args:
        image_bytes: PNG/JPEG 등 이미지 원본 바이트

    Returns:
        OCRResult: OCR 박스 목록, 엔진명, 평균 confidence, 전체 텍스트

    Raises:
        ValueError: 이미지 디코딩 실패 시
    """
    # bytes → numpy array
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
      raise ValueError(
          '이미지 디코딩 실패: 지원되지 않는 포맷이거나 손상된 파일'
      )

    raw_result = self._ocr.ocr(img, cls=True)

    boxes: list[OCRBox] = []
    # PaddleOCR 반환 형식: [[[bbox], (text, confidence)], ...]
    # 페이지 단위로 한 번 더 감싸져 있으므로 raw_result[0] 사용
    page_results = raw_result[0] if raw_result else []
    if page_results is None:
      page_results = []

    for item in page_results:
      bbox, (text, conf) = item
      boxes.append(
          OCRBox(
              text=text,
              confidence=float(conf),
              bbox=bbox,
              source='paddle',
          )
      )

    avg_conf = sum(b.confidence for b in boxes) / len(boxes) if boxes else 0.0
    raw_text = '\n'.join(b.text for b in boxes)

    logger.info(
        'OCR 완료: boxes=%d, avg_confidence=%.3f', len(boxes), avg_conf
    )

    return OCRResult(
        boxes=boxes,
        engine='PaddleOCR',
        avg_confidence=avg_conf,
        raw_text=raw_text,
    )
