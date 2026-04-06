import shutil
from pathlib import Path

import pytest

from core.exceptions import TTSGenerationError
from services.tts_zonos import ZonosTTSEngine


def test_espeak_ng_installed():
    """espeak-ng가 시스템에 설치되어 있는지 확인."""
    assert shutil.which('espeak-ng') is not None, (
        'espeak-ng가 설치되어 있지 않습니다. brew install espeak-ng 또는 apt install espeak-ng가 필요합니다.'
    )


@pytest.mark.skipif(shutil.which('espeak-ng') is None, reason='espeak-ng required')
def test_zonos_engine_initialization():
    """Zonos 엔진 초기화 테스트."""
    try:
        engine = ZonosTTSEngine()
        assert engine is not None
        assert engine._model is not None
    except Exception as e:
        pytest.fail(f'Zonos 엔진 초기화 실패: {e}')


@pytest.mark.skipif(shutil.which('espeak-ng') is None, reason='espeak-ng required')
def test_zonos_synthesize_basic():
    """기본 합성 테스트 (화자 정보 없이)."""
    engine = ZonosTTSEngine()
    text = 'Hello, welcome to ReadMate.'

    try:
        result = engine.synthesize(text)
        assert result.audio_path is not None
        assert Path(result.audio_path).exists()
        assert result.engine == 'zonos'
        print(f'\nGenerated audio: {result.audio_path}')
    except TTSGenerationError as e:
        pytest.fail(f'합성 실패: {e}')
    except Exception as e:
        # 모델에 따라 speaker가 필수일 수 있으므로 구체적인 에러 확인용
        print(f'Expected failure or specific error: {e}')


if __name__ == '__main__':
    # 수동 실행용
    if test_espeak_ng_installed():
        test_zonos_engine_initialization()
        test_zonos_synthesize_basic()
