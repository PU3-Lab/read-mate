"""Streamlit 앱 입력 변환 테스트."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from models.schemas import InputType

APP_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'app.py'
SPEC = importlib.util.spec_from_file_location('readmate_app', APP_PATH)
assert SPEC is not None
assert SPEC.loader is not None
APP_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(APP_MODULE)

build_input_payload = APP_MODULE.build_input_payload
infer_input_type = APP_MODULE.infer_input_type


def test_infer_input_type_for_pdf() -> None:
    """PDF 파일은 PDF 입력으로 판별한다."""
    assert infer_input_type('sample.pdf') is InputType.PDF


def test_infer_input_type_for_audio() -> None:
    """오디오 파일은 AUDIO 입력으로 판별한다."""
    assert infer_input_type('lecture.m4a') is InputType.AUDIO


def test_build_input_payload_normalizes_optional_fields() -> None:
    """질문과 voice preset 공백을 정리한다."""
    payload = build_input_payload(
        file_name='note.png',
        content=b'image',
        question='  ',
        voice_preset='  ',
    )

    assert payload.input_type is InputType.IMAGE
    assert payload.question is None
    assert payload.voice_preset == 'default'


def test_infer_input_type_raises_for_unsupported_file() -> None:
    """지원하지 않는 파일 형식은 예외 처리한다."""
    with pytest.raises(ValueError, match='지원하지 않는 파일 형식'):
        infer_input_type('archive.zip')
