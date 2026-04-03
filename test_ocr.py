import io

from pdf2image import convert_from_bytes

from src.services.ocr_service import Qwen2VLEngine

ocr = Qwen2VLEngine()

with open('notebooks/hyunwook/test1_2.pdf', 'rb') as f:
    pdf_bytes = f.read()

POPPLER_PATH = r'C:\Release-25.12.0-0\poppler-25.12.0\Library\bin'
images = convert_from_bytes(pdf_bytes, dpi=200, poppler_path=POPPLER_PATH)

for i, img in enumerate(images):
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    result = ocr.recognize(buf.getvalue())
    print(f'=== 페이지 {i + 1} ===')
    print(f'엔진: {result.engine}')
    print(f'신뢰도: {result.avg_confidence}')
    print(f'텍스트:\n{result.raw_text}\n')
