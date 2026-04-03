"""
Zonos TTS 목소리 확인용 테스트 스크립트.
"""

import os
import subprocess
import sys

from services.tts_zonos import ZonosTTSEngine


def check_voice(text: str = None, voice_preset: str = None):
    """
    텍스트를 입력받아 음성을 생성하고 확인한다.
    """
    if not text:
        text = '안녕하세요. Zonos TTS 엔진 테스트 중입니다. 목소리가 잘 들리나요?'

    print('--- Zonos TTS 목소리 확인 ---')
    print(f'입력 텍스트: {text}')
    if voice_preset:
        print(f'화자 프리셋(참조): {voice_preset}')

    print('\n모델 로드 중... (처음 실행 시 시간이 걸릴 수 있습니다)')
    try:
        engine = ZonosTTSEngine()

        print('음성 합성 중...')
        result = engine.synthesize(text, voice_preset=voice_preset or 'default')

        audio_path = result.audio_path
        print('\n✅ 음성 생성 성공!')
        print(f'저장 위치: {audio_path}')
        print(f'재생 시간: {result.duration_sec}초')

        # 운영체제별 기본 플레이어로 자동 재생 시도
        if sys.platform == 'darwin':
            print('\n시스템 기본 플레이어로 재생합니다...')
            subprocess.run(['open', audio_path], check=False)
        elif sys.platform == 'win32':
            print('\n시스템 기본 플레이어로 재생합니다...')
            os.startfile(audio_path)
        else:
            print(f'\n파일을 직접 열어서 확인해 주세요: {audio_path}')

    except Exception as e:
        print(f'\n❌ 오류 발생: {e}')


if __name__ == '__main__':
    # 실행 시 인자로 텍스트를 받을 수도 있음
    # 예: uv run scripts/check_voice.py "원하는 문구" "참조_목소리.wav"
    input_text = sys.argv[1] if len(sys.argv) > 1 else None
    preset = sys.argv[2] if len(sys.argv) > 2 else None

    check_voice(input_text, preset)
