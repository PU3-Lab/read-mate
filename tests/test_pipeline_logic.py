from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from models.schemas import (  # noqa: E402
    InputPayload,
    InputType,
    LLMResult,
    OCRResult,
    PDFResult,
    PipelineStatus,
    TaskType,
    TTSResult,
)
from pipelines.reading_pipeline import ReadingPipeline  # noqa: E402
from services.base import BaseLLM, BaseOCR, BasePDF, BaseSTT, BaseTTS  # noqa: E402
from services.llm_base import ChunkedLLM  # noqa: E402
from services.pdf_service import PyPDFEngine  # noqa: E402


class DummyOCR(BaseOCR):
    def recognize(self, image_bytes: bytes) -> OCRResult:
        return OCRResult(boxes=[], engine='dummy-ocr', avg_confidence=1.0, raw_text='ocr')


class DummyPDF(BasePDF):
    def extract(self, pdf_bytes: bytes) -> PDFResult:
        return PDFResult(text='pdf text', page_count=1, is_scanned=False)


class DummySTT(BaseSTT):
    def transcribe(self, audio_bytes: bytes):
        raise NotImplementedError


class DummyLLM(BaseLLM):
    def __init__(self) -> None:
        self.calls: list[tuple[str, TaskType, str | None]] = []

    def generate(
        self, text: str, task: TaskType, question: str | None = None
    ) -> LLMResult:
        self.calls.append((text, task, question))
        return LLMResult(
            summary='summary',
            key_points=['point'],
            qa_answer='answer' if task is TaskType.QA else None,
            engine='dummy-llm',
        )


class DummyTTS(BaseTTS):
    def synthesize(self, text: str, voice_preset: str = 'default') -> TTSResult:
        return TTSResult(
            audio_path='/tmp/fake.wav',
            voice_preset=voice_preset,
            engine='dummy-tts',
            duration_sec=0.1,
        )

    def list_presets(self) -> list[str]:
        return ['default']


class FakeChunkedLLM(ChunkedLLM):
    max_input_chars = 5

    def __init__(self) -> None:
        self.calls: list[tuple[str, TaskType, str | None]] = []

    def _generate_single(
        self, text: str, task: TaskType, question: str | None
    ) -> LLMResult:
        self.calls.append((text, task, question))
        return LLMResult(
            summary=f'summary:{text}',
            key_points=[text],
            qa_answer=f'qa:{text}' if task is TaskType.QA else None,
            engine='fake',
        )

    def _build_fallback_result(
        self, task: TaskType, question: str | None
    ) -> LLMResult:
        return LLMResult(summary='fallback', key_points=['fallback'], engine='fake')

    def _chunk_text(self, text: str) -> list[str]:
        return [
            'alpha beta',
            'epsilon zeta',
            'theta iota',
        ]


class ReadingPipelineTests(unittest.TestCase):
    def test_question_input_uses_context_text(self) -> None:
        llm = DummyLLM()
        pipeline = ReadingPipeline(
            ocr=DummyOCR(),
            pdf=DummyPDF(),
            stt=DummySTT(),
            llm=llm,
            tts=DummyTTS(),
        )

        result = pipeline.run(
            InputPayload(
                input_type=InputType.QUESTION,
                file_name='question.txt',
                content=b'',
                question='핵심이 뭐야?',
                context_text='이 문서는 테스트용 본문입니다.',
            )
        )

        self.assertEqual(result.status, PipelineStatus.SUCCESS)
        self.assertEqual(llm.calls[0][0], '이 문서는 테스트용 본문입니다.')
        self.assertEqual(llm.calls[0][1], TaskType.QA)
        self.assertEqual(llm.calls[0][2], '핵심이 뭐야?')

    def test_question_input_requires_context_text(self) -> None:
        pipeline = ReadingPipeline(
            ocr=DummyOCR(),
            pdf=DummyPDF(),
            stt=DummySTT(),
            llm=DummyLLM(),
            tts=DummyTTS(),
        )

        result = pipeline.run(
            InputPayload(
                input_type=InputType.QUESTION,
                file_name='question.txt',
                content=b'',
                question='핵심이 뭐야?',
            )
        )

        self.assertEqual(result.status, PipelineStatus.FAILED)
        self.assertIn('context_text', result.warnings[0])


class ChunkedLLMTests(unittest.TestCase):
    def test_long_qa_uses_relevant_raw_chunks(self) -> None:
        llm = FakeChunkedLLM()

        result = llm.generate(
            'unused source text',
            TaskType.QA,
            question='epsilon 의미가 뭐야?',
        )

        self.assertEqual(result.qa_answer, 'qa:epsilon zeta')
        self.assertEqual(len(llm.calls), 1)
        self.assertEqual(llm.calls[0][1], TaskType.QA)


class PyPDFEngineTests(unittest.TestCase):
    def test_short_pdf_keeps_pypdf_text_when_ocr_fallback_returns_empty(self) -> None:
        engine = PyPDFEngine(ocr_fallback=DummyOCR())

        pdf_buffer = io.BytesIO()
        image = Image.new('RGB', (10, 10), 'white')
        image.save(pdf_buffer, format='PDF')

        class FakePage:
            @staticmethod
            def extract_text() -> str:
                return '짧은 텍스트'

        class FakeReader:
            def __init__(self, _stream: io.BytesIO) -> None:
                self.pages = [FakePage()]

        with patch('services.pdf_service.PdfReader', FakeReader):
            with patch.object(PyPDFEngine, '_ocr_all_pages', return_value=''):
                result = engine.extract(pdf_buffer.getvalue())

        self.assertEqual(result.text, '[페이지 1]\n짧은 텍스트')
        self.assertFalse(result.is_scanned)


if __name__ == '__main__':
    unittest.main()
