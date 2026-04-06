import os
import re
import shutil
import subprocess
import tempfile

import whisper
import yt_dlp

from lib.utils.path import data_path
from models.schemas import STTResult, STTSegment
from services.base import BaseSTT


class ReadMateSTT(BaseSTT):
    """openai-whisper 기반 STT 엔진."""

    def __init__(self, model_size: str = 'medium') -> None:
        """Whisper 모델을 로드한다."""
        print(f'>>> Whisper 모델({model_size}) 로딩 중...')
        self.model = whisper.load_model(model_size)

    def transcribe(self, audio_bytes: bytes) -> STTResult:
        """오디오 바이트를 텍스트로 변환한다."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_raw:
            tmp_raw.write(audio_bytes)
            tmp_raw_path = tmp_raw.name

        processed_path = None
        try:
            processed_path = self._preprocess_audio(tmp_raw_path)

            result = self.model.transcribe(
                processed_path,
                fp16=False,
                language='ko',
                beam_size=5,
                best_of=5,
                temperature=0.0,
                condition_on_previous_text=False,
                no_speech_threshold=0.6,
                compression_ratio_threshold=2.4,
            )

            cleaned_text = self._clean_text(result['text'])
            segments = self._normalize_segments(result.get('segments', []))

            return STTResult(
                text=cleaned_text,
                language=result.get('language', 'ko'),
                segments=segments,
                engine='whisper',
            )

        finally:
            for path in [tmp_raw_path, processed_path]:
                if path and os.path.exists(path):
                    os.remove(path)

    def run_pipeline(
        self,
        youtube_url: str,
        output_file: str = 'moonanbaseball_lecture_output.txt',
    ) -> STTResult | None:
        """유튜브 URL에서 오디오를 추출한 뒤 STT를 수행한다."""
        audio_file = None
        try:
            audio_file = self._extract_from_youtube(youtube_url)

            with open(audio_file, 'rb') as f:
                audio_bytes = f.read()

            stt_result = self.transcribe(audio_bytes)

            print('\n' + '=' * 100)
            print('[최종 추출 결과]')
            print(stt_result.text[:300] + '...')
            print('=' * 100)

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(stt_result.text)

            return stt_result

        except Exception as e:
            print(f'!!! 오류 발생: {e}')
            return None

        finally:
            if audio_file and os.path.exists(audio_file):
                os.remove(audio_file)

    def _extract_from_youtube(self, url: str) -> str:
        """유튜브에서 오디오를 WAV로 추출한다."""
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, 'target_audio')

        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            }],
            'outtmpl': output_path,
            'quiet': True,
        }

        print(f'>>> 유튜브 오디오 추출 시작: {url}')
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        return f'{output_path}.wav'

    def _preprocess_audio(self, input_path: str) -> str:
        """ffmpeg로 STT 입력용 오디오를 전처리한다."""
        if shutil.which('ffmpeg') is None:
            print('>>> ffmpeg 미설치: 원본 오디오로 진행')
            return input_path

        output_path = input_path.replace('.wav', '_processed.wav')
        print('>>> 오디오 전처리 중...')
        subprocess.run([
            'ffmpeg', '-i', input_path,
            '-ar', '16000',
            '-ac', '1',
            '-af', 'loudnorm',
            output_path, '-y', '-q:a', '0',
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_path

    def _clean_text(self, text: str) -> str:
        """불필요한 추임새와 공백을 정리한다."""
        cleaned = re.sub(r'\b(어+|음+|아+|그+|저+|에+)\b', '', text)
        return re.sub(r'\s+', ' ', cleaned).strip()

    def _normalize_segments(self, raw_segments: list[dict]) -> list[STTSegment]:
        """Whisper 원본 세그먼트를 STTSegment로 변환한다."""
        return [
            STTSegment(
                start=round(float(segment.get('start', 0.0)), 2),
                end=round(float(segment.get('end', 0.0)), 2),
                text=str(segment.get('text', '')).strip(),
            )
            for segment in raw_segments
        ]


if __name__ == '__main__':
    stt_worker = ReadMateSTT(model_size='medium')
    test_url = 'https://youtu.be/7E4DfSFMcwU?si=ZjyQIcXaHUXUv8BD'
    stt_worker.run_pipeline(test_url, data_path() / 'moonanbaseball_lecture_output.txt')
