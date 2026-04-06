# # import sys
# # import os

# # from lib.utils.path import data_path
# # sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# # import whisper
# # import yt_dlp
# # import re
# # import subprocess
# # import tempfile

# # from models.schemas import STTResult
# # from services.base import BaseSTT


# # class ReadMateSTT(BaseSTT):
# #     def __init__(self, model_size: str = "medium"):
# #         print(f">>> Whisper 모델({model_size}) 로딩 중...")
# #         self.model = whisper.load_model(model_size)

# #     def transcribe(self, audio_bytes: bytes) -> STTResult:
# #         with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_raw:
# #             tmp_raw.write(audio_bytes)
# #             tmp_raw_path = tmp_raw.name

# #         processed_path = None
# #         try:
# #             processed_path = self._preprocess_audio(tmp_raw_path)

# #             result = self.model.transcribe(
# #                 processed_path,
# #                 fp16=False,
# #                 language="ko",
# #                 beam_size=5,
# #                 best_of=5,
# #                 temperature=0.0,
# #                 condition_on_previous_text=False,
# #                 no_speech_threshold=0.6,
# #                 compression_ratio_threshold=2.4,
# #             )

# #             cleaned_text = self._clean_text(result["text"])

# #             return STTResult(
# #                 text=cleaned_text,
# #                 language=result.get("language", "ko"),
# #                 segments=result.get("segments", []),
# #                 engine="whisper",
# #             )

# #         finally:
# #             for path in [tmp_raw_path, processed_path]:
# #                 if path and os.path.exists(path):
# #                     os.remove(path)

# #     def run_pipeline(self, youtube_url: str, output_file: str = "moonanbaseball_lecture_output.txt") -> STTResult | None:
# #         audio_file = None
# #         try:
# #             audio_file = self._extract_from_youtube(youtube_url)

# #             with open(audio_file, "rb") as f:
# #                 audio_bytes = f.read()

# #             stt_result = self.transcribe(audio_bytes)

# #             print("\n" + "=" * 100)
# #             print("[최종 추출 결과]")
# #             print(stt_result.text[:300] + "...")
# #             print("=" * 100)

# #             with open(output_file, "w", encoding="utf-8") as f:
# #                 f.write(stt_result.text)

# #             return stt_result

# #         except Exception as e:
# #             print(f"!!! 오류 발생: {e}")
# #             return None

# #         finally:
# #             if audio_file and os.path.exists(audio_file):
# #                 os.remove(audio_file)

# #     def create_sample(self, youtube_url: str, duration: int = 20, output_file: str = None) -> str | None:
# #         """유튜브에서 오디오를 추출해 지정한 길이(초)만큼 잘라 샘플 wav 파일 생성"""
# #         if output_file is None:
# #             output_file = str(data_path() / "sample.wav")

# #         audio_file = None
# #         try:
# #             audio_file = self._extract_from_youtube(youtube_url)

# #             print(f">>> {duration}초 샘플 생성 중...")
# #             subprocess.run([
# #                 "ffmpeg", "-i", audio_file,
# #                 "-t", str(duration),
# #                 "-ar", "16000",
# #                 "-ac", "1",
# #                 "-af", "loudnorm",
# #                 output_file, "-y", "-q:a", "0"
# #             ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# #             print(f">>> 샘플 파일 저장 완료: {output_file}")
# #             return output_file

# #         except Exception as e:
# #             print(f"!!! 샘플 생성 오류: {e}")
# #             return None

# #         finally:
# #             if audio_file and os.path.exists(audio_file):
# #                 os.remove(audio_file)

# #     def _extract_from_youtube(self, url: str) -> str:
# #         temp_dir = tempfile.mkdtemp()
# #         output_path = os.path.join(temp_dir, "target_audio")

# #         ydl_opts = {
# #             "format": "bestaudio/best",
# #             "postprocessors": [{
# #                 "key": "FFmpegExtractAudio",
# #                 "preferredcodec": "wav",
# #             }],
# #             "outtmpl": output_path,
# #             "quiet": True,
# #         }

# #         print(f">>> 유튜브 오디오 추출 시작: {url}")
# #         with yt_dlp.YoutubeDL(ydl_opts) as ydl:
# #             ydl.download([url])

# #         return f"{output_path}.wav"

# #     def _preprocess_audio(self, input_path: str) -> str:
# #         output_path = input_path.replace(".wav", "_processed.wav")
# #         print(">>> 오디오 전처리 중...")
# #         subprocess.run([
# #             "ffmpeg", "-i", input_path,
# #             "-ar", "16000",
# #             "-ac", "1",
# #             "-af", "loudnorm",
# #             output_path, "-y", "-q:a", "0"
# #         ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
# #         return output_path

# #     def _clean_text(self, text: str) -> str:
# #         cleaned = re.sub(r"\b(어+|음+|아+|그+|저+|에+)\b", "", text)
# #         return re.sub(r"\s+", " ", cleaned).strip()


# # if __name__ == "__main__":
# #     stt_worker = ReadMateSTT(model_size="medium")
# #     test_url = "https://youtu.be/2DnGKEeRB4g?si=XU-riYx-w1pCFgNU"

# #     # data 폴더에 sample.wav 저장
# #     stt_worker.create_sample(test_url, duration=20)

# #     # 전체 파이프라인 실행 (필요 시 주석 해제)
# #     # stt_worker.run_pipeline(test_url, data_path() / 'moonanbaseball_lecture_output.txt')


# # ======================================================================================================
# ## 영상 추출 원하는 지점 원할 시 

import sys
import os

from lib.utils.path import data_path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import whisper
import yt_dlp
import re
import subprocess
import tempfile

from models.schemas import STTResult
from services.base import BaseSTT


class ReadMateSTT(BaseSTT):
    def __init__(self, model_size: str = "medium"):
        print(f">>> Whisper 모델({model_size}) 로딩 중...")
        self.model = whisper.load_model(model_size)

    def transcribe(self, audio_bytes: bytes) -> STTResult:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_raw:
            tmp_raw.write(audio_bytes)
            tmp_raw_path = tmp_raw.name

        processed_path = None
        try:
            processed_path = self._preprocess_audio(tmp_raw_path)

            result = self.model.transcribe(
                processed_path,
                fp16=False,
                language="ko",
                beam_size=5,
                best_of=5,
                temperature=0.0,
                condition_on_previous_text=False,
                no_speech_threshold=0.6,
                compression_ratio_threshold=2.4,
            )

            cleaned_text = self._clean_text(result["text"])

            return STTResult(
                text=cleaned_text,
                language=result.get("language", "ko"),
                segments=result.get("segments", []),
                engine="whisper",
            )

        finally:
            for path in [tmp_raw_path, processed_path]:
                if path and os.path.exists(path):
                    os.remove(path)

    def run_pipeline(self, youtube_url: str, output_file: str = "moonanbaseball_lecture_output.txt") -> STTResult | None:
        audio_file = None
        try:
            audio_file = self._extract_from_youtube(youtube_url)

            with open(audio_file, "rb") as f:
                audio_bytes = f.read()

            stt_result = self.transcribe(audio_bytes)

            print("\n" + "=" * 100)
            print("[최종 추출 결과]")
            print(stt_result.text[:300] + "...")
            print("=" * 100)

            with open(output_file, "w", encoding="utf-8") as f:
                f.write(stt_result.text)

            return stt_result

        except Exception as e:
            print(f"!!! 오류 발생: {e}")
            return None

        finally:
            if audio_file and os.path.exists(audio_file):
                os.remove(audio_file)

    def create_sample(self, youtube_url: str, start: int = 0, duration: int = 20, output_file: str = None) -> str | None:
        """유튜브에서 오디오를 추출해 start초부터 duration초 길이만큼 잘라 샘플 wav 파일 생성"""
        if output_file is None:
            output_file = str(data_path() / "moon625.wav")

        audio_file = None
        try:
            audio_file = self._extract_from_youtube(youtube_url)

            print(f">>> {start}초 ~ {start + duration}초 샘플 생성 중...")
            subprocess.run([
                "ffmpeg", "-i", audio_file,
                "-ss", str(start),
                "-t", str(duration),
                "-ar", "16000",
                "-ac", "1",
                "-af", "loudnorm",
                output_file, "-y", "-q:a", "0"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            print(f">>> 샘플 파일 저장 완료: {output_file}")
            return output_file

        except Exception as e:
            print(f"!!! 샘플 생성 오류: {e}")
            return None

        finally:
            if audio_file and os.path.exists(audio_file):
                os.remove(audio_file)

    def _extract_from_youtube(self, url: str) -> str:
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, "target_audio")

        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
            }],
            "outtmpl": output_path,
            "quiet": True,
            "socket_timeout": 60,
            "retries": 10,
            "fragment_retries": 10,
            "extractor_args": {
                "youtube": {"skip": ["dash", "hls"]}
            },
        }

        print(f">>> 유튜브 오디오 추출 시작: {url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        return f"{output_path}.wav"

    def _preprocess_audio(self, input_path: str) -> str:
        output_path = input_path.replace(".wav", "_processed.wav")
        print(">>> 오디오 전처리 중...")
        subprocess.run([
            "ffmpeg", "-i", input_path,
            "-ar", "16000",
            "-ac", "1",
            "-af", "loudnorm",
            output_path, "-y", "-q:a", "0"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_path

    def _clean_text(self, text: str) -> str:
        cleaned = re.sub(r"\b(어+|음+|아+|그+|저+|에+)\b", "", text)
        return re.sub(r"\s+", " ", cleaned).strip()


if __name__ == "__main__":
    stt_worker = ReadMateSTT(model_size="medium")
    test_url = "https://youtu.be/VmFFlK03WHc?si=MrzEIa6CDZp9mE3A"

    # 0초 ~ 19초 구간 추출
    stt_worker.create_sample(test_url, start=1, duration=360)

    # 전체 파이프라인 실행 (필요 시 주석 해제)
    # stt_worker.run_pipeline(test_url, data_path() / 'moonanbaseball_lecture_output.txt')

# ###############################################################################################
# ###############################################################################################
# ### audio volume up ###

# import subprocess
# import os
# from lib.utils.path import data_path

# def boost_volume(input_file: str, output_file: str, volume: float = 2.0):
#     """기존 wav 파일의 볼륨을 키워서 저장"""
#     print(f">>> 볼륨 x{volume} 적용 중: {input_file}")
#     subprocess.run([
#         "ffmpeg", "-i", input_file,
#         "-af", f"loudnorm,volume={volume}",
#         "-ar", "16000",
#         "-ac", "1",
#         output_file, "-y", "-q:a", "0"
#     ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
#     print(f">>> 저장 완료: {output_file}")


# if __name__ == "__main__":
#     data = data_path()

#     files = ["samplekang.wav"]

#     for filename in files:
#         input_path  = str(data / filename)
#         output_path = str(data / filename.replace(".wav", "_boosted.wav"))
#         boost_volume(input_path, output_path, volume=2.0)