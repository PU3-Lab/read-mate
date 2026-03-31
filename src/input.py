"""입력 수신 모듈 — 이미지/PDF 분기 처리."""

from pathlib import Path

import streamlit as st
from PIL import Image


def load_from_camera() -> Image.Image | None:
    """카메라로 책 페이지를 촬영하여 PIL Image로 반환."""
    img_file = st.camera_input('책 페이지를 촬영하세요')
    if img_file is None:
        return None
    return Image.open(img_file)


def load_from_upload() -> Image.Image | list[Image.Image] | None:
    """파일 업로드를 통해 이미지 또는 PDF를 로드.

    Returns:
        이미지 파일: PIL Image
        PDF 파일: 페이지별 PIL Image 리스트
        업로드 없음: None
    """
    uploaded = st.file_uploader(
        '이미지 또는 PDF를 업로드하세요',
        type=['jpg', 'jpeg', 'png', 'pdf'],
    )
    if uploaded is None:
        return None

    if uploaded.type == 'application/pdf':
        return _pdf_to_images(uploaded.read())

    return Image.open(uploaded)


def _pdf_to_images(pdf_bytes: bytes) -> list[Image.Image]:
    """PDF bytes를 페이지별 PIL Image 리스트로 변환."""
    import pdf2image  # lazy import

    return pdf2image.convert_from_bytes(pdf_bytes)
