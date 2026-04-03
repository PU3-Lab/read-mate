"""
Zonos TTS 목소리 일괄 등록 스크립트.
data/voices 폴더 내의 모든 음성 파일(.wav, .mp3 등)을 읽어
화자 임베딩(.pt) 가중치 파일로 일괄 변환하여 저장합니다.
"""

import os
import sys

from core.config import VOICES_DIR
from services.tts_zonos import ZonosTTSEngine


def register_all_voices():
    """
    data/voices 내의 음성 파일들을 찾아 임베딩 파일로 변환한다.
    """
    print('--- Zonos 목소리 일괄 등록 시작 ---')
    print(f'대상 폴더: {VOICES_DIR}')

    # 지원하는 오디오 확장자
    audio_exts = ['.wav', '.mp3', '.m4a', '.flac']

    # 처리할 파일 목록 수집
    audio_files = [f for f in VOICES_DIR.iterdir() if f.suffix.lower() in audio_exts]

    if not audio_files:
        print('등록할 음성 파일이 없습니다. data/voices 폴더에 .wav 파일을 넣어주세요.')
        return

    print(f'발견된 음성 파일: {len(audio_files)}개')

    print('\n모델 로드 중...')
    try:
        engine = ZonosTTSEngine()

        success_count = 0
        skip_count = 0

        for audio_file in audio_files:
            weight_file = VOICES_DIR / f'{audio_file.stem}.pt'

            # 이미 가중치 파일이 있으면 건너뜀
            if weight_file.exists():
                print(
                    f"[-] '{audio_file.name}' 은(는) 이미 등록되어 있습니다. (건너뜀)"
                )
                skip_count += 1
                continue

            print(f"[+] '{audio_file.name}' 처리 중...", end='', flush=True)
            try:
                # _get_speaker_embedding 호출 시 자동으로 .pt 저장 로직이 포함됨
                engine._get_speaker_embedding(str(audio_file))
                print(' 완료!')
                success_count += 1
            except Exception as e:
                print(f' 실패: {e}')

        print('\n--- 등록 완료 ---')
        print(f'새로 등록됨: {success_count}개')
        print(f'이미 존재함: {skip_count}개')
        print(f'현재 총 목소리 수: {len(engine.list_presets())}개')

    except Exception as e:
        print(f'\n❌ 모델 로드 중 오류 발생: {e}')


if __name__ == '__main__':
    register_all_voices()
