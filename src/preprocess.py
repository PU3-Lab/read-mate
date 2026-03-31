"""이미지 전처리 모듈 — OpenCV 기반 기울기 보정 및 노이즈 제거."""

import cv2
import numpy as np
from PIL import Image


def preprocess(image: Image.Image) -> np.ndarray:
    """전처리 파이프라인 실행.

    순서: 그레이스케일 → 기울기 보정 → 노이즈 제거 → 대비 강화 → 이진화

    Args:
        image: 입력 PIL Image

    Returns:
        전처리된 numpy array (grayscale)
    """
    img = np.array(image)
    img = _to_grayscale(img)
    img = _deskew(img)
    img = _denoise(img)
    img = _enhance_contrast(img)
    img = _binarize(img)
    return img


def _to_grayscale(img: np.ndarray) -> np.ndarray:
    """RGB → 그레이스케일 변환."""
    if len(img.shape) == 3:
        return cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    return img


def _deskew(img: np.ndarray) -> np.ndarray:
    """텍스트 기울기 보정."""
    coords = np.column_stack(np.where(img < 128))
    if len(coords) == 0:
        return img
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    (h, w) = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def _denoise(img: np.ndarray) -> np.ndarray:
    """가우시안 블러로 노이즈 제거."""
    return cv2.GaussianBlur(img, (3, 3), 0)


def _enhance_contrast(img: np.ndarray) -> np.ndarray:
    """CLAHE로 대비 강화."""
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(img)


def _binarize(img: np.ndarray) -> np.ndarray:
    """Adaptive Threshold로 이진화."""
    return cv2.adaptiveThreshold(
        img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
