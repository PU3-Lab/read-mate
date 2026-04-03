# tests/test_stt_whisper.py

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import MagicMock, patch

import pytest

from models.schemas import STTResult
from services.stt_whisper_service import ReadMateSTT

# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------


@pytest.fixture
def stt(tmp_path):
    """ReadMateSTT 인스턴스 (Whisper 모델 로딩 mock)"""
    with patch('whisper.load_model', return_value=MagicMock()):
        worker = ReadMateSTT(model_size='base')
    return worker


def make_mock_transcribe_result(
    text: str = '안녕하세요 테스트입니다', language: str = 'ko'
):
    """model.transcribe() 반환값 mock"""
    return {
        'text': text,
        'language': language,
        'segments': [{'start': 0.0, 'end': 1.0, 'text': text}],
    }


# -----------------------------------------------------------------------
# transcribe() 테스트
# -----------------------------------------------------------------------


def test_transcribe_returns_stt_result(stt):
    """transcribe()가 STTResult를 반환하는지 확인"""
    stt.model.transcribe.return_value = make_mock_transcribe_result()

    dummy_audio = b'\x00' * 1024
    result = stt.transcribe(dummy_audio)

    assert isinstance(result, STTResult)
    assert result.engine == 'whisper'
    assert result.language == 'ko'
    assert isinstance(result.text, str)


def test_transcribe_cleans_fillers(stt):
    """추임새가 제거되는지 확인"""
    stt.model.transcribe.return_value = make_mock_transcribe_result(
        text='어 오늘은 음 파이썬을 배워보겠습니다'
    )

    result = stt.transcribe(b'\x00' * 1024)

    assert '어' not in result.text.split()
    assert '음' not in result.text.split()


def test_transcribe_text_not_empty(stt):
    """결과 텍스트가 비어있지 않은지 확인"""
    stt.model.transcribe.return_value = make_mock_transcribe_result(
        text='강의 내용입니다'
    )

    result = stt.transcribe(b'\x00' * 1024)
    assert len(result.text.strip()) > 0


# -----------------------------------------------------------------------
# _clean_text() 테스트
# -----------------------------------------------------------------------


def test_clean_text_removes_fillers(stt):
    raw = '어 오늘은 그 파이썬 강의입니다 음 시작하겠습니다'
    cleaned = stt._clean_text(raw)
    for filler in ['어', '음', '그']:
        assert filler not in cleaned.split()


def test_clean_text_preserves_meaning(stt):
    """의미 있는 단어는 보존되는지 확인"""
    raw = '오늘은 파이썬을 공부합니다'
    cleaned = stt._clean_text(raw)
    assert '파이썬' in cleaned
    assert '공부합니다' in cleaned


# -----------------------------------------------------------------------
# run_pipeline() 테스트
# -----------------------------------------------------------------------


def test_run_pipeline_returns_stt_result(stt, tmp_path):
    """run_pipeline()이 STTResult를 반환하는지 확인"""
    stt.model.transcribe.return_value = make_mock_transcribe_result()

    fake_wav = tmp_path / 'audio.wav'
    fake_wav.write_bytes(b'\x00' * 1024)

    with (
        patch.object(stt, '_extract_from_youtube', return_value=str(fake_wav)),
        patch.object(stt, '_preprocess_audio', return_value=str(fake_wav)),
    ):
        output_file = str(tmp_path / 'output.txt')
        result = stt.run_pipeline('https://youtu.be/dummy', output_file=output_file)

    assert isinstance(result, STTResult)
    assert os.path.exists(output_file)


def test_run_pipeline_saves_output_file(stt, tmp_path):
    """출력 파일이 실제로 저장되는지 확인"""
    stt.model.transcribe.return_value = make_mock_transcribe_result(text='저장 테스트')

    fake_wav = tmp_path / 'audio.wav'
    fake_wav.write_bytes(b'\x00' * 1024)

    output_file = str(tmp_path / 'result.txt')

    with (
        patch.object(stt, '_extract_from_youtube', return_value=str(fake_wav)),
        patch.object(stt, '_preprocess_audio', return_value=str(fake_wav)),
    ):
        stt.run_pipeline('https://youtu.be/dummy', output_file=output_file)

    with open(output_file, encoding='utf-8') as f:
        content = f.read()

    assert len(content) > 0


def test_run_pipeline_returns_none_on_error(stt):
    """오류 발생 시 None을 반환하는지 확인"""
    with patch.object(
        stt, '_extract_from_youtube', side_effect=Exception('다운로드 실패')
    ):
        result = stt.run_pipeline('https://youtu.be/invalid')

    assert result is None
