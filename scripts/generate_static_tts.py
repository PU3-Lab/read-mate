import shutil

from lib.utils.path import root
from services.tts_elevenlabs import ElevenLabsTTS


def generate_static_audio():
    tts = ElevenLabsTTS()

    tasks = [
        ('잠시만 기다려 주세요', 'data/static_tts/common/wait_moment.mp3'),
        (
            '분석을 시작합니다. 잠시만 기다려 주세요',
            'data/static_tts/common/start_analysis_wait.mp3',
        ),
    ]

    for text, relative_path in tasks:
        print(f"Generating audio for: '{text}' -> {relative_path}")
        result = tts.synthesize(text)

        target_path = root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # 임시 파일을 타겟 위치로 이동
        shutil.copy(result.audio_path, target_path)
        print(f'Saved to {target_path}')


if __name__ == '__main__':
    generate_static_audio()
