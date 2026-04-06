"""
Qwen2.5-VL 기반 OCR 엔진 구현.
VLM(Vision Language Model)으로 한국어/영어 텍스트 인식.
4-bit 양자화로 8GB VRAM에서 동작 가능.
싱글톤 패턴으로 모델 재로드 방지.

접근성 모드: 이미지 유형 자동 분류 후 시각장애인을 위한 묘사 텍스트 생성.
"""

import logging
from io import BytesIO
from threading import Lock

import torch
from PIL import Image
from qwen_vl_utils import process_vision_info
from transformers import (
    AutoProcessor,
    BitsAndBytesConfig,
    Qwen2_5_VLForConditionalGeneration,
)

from lib.utils.device import available_device
from models.schemas import ImageType, OCRBox, OCRResult
from services.base import BaseOCR

logger = logging.getLogger(__name__)

_MODEL_ID = 'Qwen/Qwen2.5-VL-7B-Instruct'

# 기존 텍스트 추출 프롬프트
_OCR_PROMPT = (
    '이 이미지에서 모든 텍스트를 추출하세요. 텍스트만 출력하고 다른 설명은 하지 마세요.'
)

# 1차 분류 프롬프트
_CLASSIFY_PROMPT = """이 이미지를 분석해서 아래 중 하나로만 답하세요.
- table: 행과 열로 구성된 표
- anatomy: 인체 해부도, 경혈 위치도, 근육도 등 신체 관련 그림
- photo: 역사 그림, 풍경, 인물 등 일반 사진 또는 분류 불확실한 경우

반드시 table / anatomy / photo 중 하나만 출력하세요."""

# 2차 처리 프롬프트: 표 선형화
_TABLE_PROMPT = """당신은 시각장애인을 위한 표 해설사입니다.
이 표를 화면낭독기로 듣기 좋도록 선형화하세요.

규칙:
- "(열 제목): (내용)" 형태로 각 셀을 풀어서 서술
- 행마다 줄바꿈으로 구분
- 병합 셀은 해당 행에 반복 서술
- 괄호, 특수기호 최소화

예시:
경혈명: 합곡. 위치: 엄지와 검지 사이 살집 부분. 효능: 두통과 치통 완화."""

# 2차 처리 프롬프트: 해부도/경혈도
_ANATOMY_PROMPT = """당신은 시각장애인 안마사 학생을 가르치는 해부학 선생님입니다.
학생은 눈이 보이지 않으며, 플라스틱 신체 모형을 손으로 만지며 학습합니다.

이 그림을 다음 규칙에 따라 설명하세요:

1. 첫 문장: 이 그림이 무엇인지 한 문장으로 요약
2. 전체 구조: 위에서 아래, 또는 중심에서 바깥 순서로 위치 관계 서술
3. 위치 표현: "자신의 왼쪽", "머리 방향으로", "손가락 두 마디 아래" 등 신체 기준 사용
4. 모형 실습: "모형에서 ~을 손으로 찾으세요" 형태로 1~2회 포함
5. 촉각 실습: 자기 몸을 만지며 확인할 수 있으면 포함
6. 문장은 짧고 명확하게, 한 문장에 하나의 정보만

출력 형식:
그림 설명 시작.
(설명 내용)
그림 설명 끝."""

# 2차 처리 프롬프트: 일반 사진 (폴백 포함)
_PHOTO_PROMPT = """당신은 시각장애인을 위한 이미지 해설사입니다.
이 이미지에 무엇이 있는지 시각장애인이 머릿속으로 장면을 그릴 수 있도록 설명하세요.

규칙:
- 전체 장면을 먼저 한 문장으로 요약
- 중요한 요소를 위치 관계와 함께 서술 (왼쪽, 오른쪽, 앞, 뒤, 위, 아래)
- 색상, 형태, 분위기 포함
- 텍스트가 있으면 텍스트도 포함
- 3~6문장으로 간결하게

출력 형식:
그림 설명 시작.
(설명 내용)
그림 설명 끝."""

_PROMPT_MAP: dict[ImageType, str] = {
    ImageType.TABLE: _TABLE_PROMPT,
    ImageType.ANATOMY: _ANATOMY_PROMPT,
    ImageType.PHOTO: _PHOTO_PROMPT,
}


class Qwen2VLEngine(BaseOCR):
    """
    Qwen2.5-VL-7B 기반 한국어/영어 OCR 엔진.
    4-bit NF4 양자화로 ~5-6GB VRAM 사용.
    싱글톤 패턴으로 모델을 한 번만 로드.

    접근성 모드: 이미지 유형을 자동 분류하여 시각장애인에 최적화된 묘사 텍스트 생성.
    """

    _instance: 'Qwen2VLEngine | None' = None
    _lock: Lock = Lock()

    def __new__(cls) -> 'Qwen2VLEngine':
        """싱글톤 인스턴스 반환."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._model = None
                cls._instance._processor = None
                cls._instance._device = None
                cls._instance._init_model()
        return cls._instance

    def _init_model(self) -> None:
        """
        Qwen2.5-VL 모델 초기화.
        4-bit NF4 양자화 적용, available_device()로 디바이스 자동 감지.
        """
        self._device = available_device()
        dtype = torch.bfloat16 if self._device != 'cpu' else torch.float32

        logger.info('Qwen2.5-VL 초기화: device=%s dtype=%s', self._device, dtype)

        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=dtype,
            bnb_4bit_quant_type='nf4',
            bnb_4bit_use_double_quant=True,
        )

        try:
            self._model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                _MODEL_ID,
                quantization_config=bnb_config,
                device_map='auto',
                torch_dtype=dtype,
            )
            self._processor = AutoProcessor.from_pretrained(_MODEL_ID)
            logger.info('Qwen2.5-VL 모델 로드 성공')
        except Exception as e:
            logger.error('Qwen2.5-VL 모델 로드 실패: %s', str(e))
            raise RuntimeError(f'Qwen2.5-VL 초기화 실패\n오류: {str(e)[:200]}') from e

    def unload(self) -> None:
        """
        VRAM 절약을 위해 모델 언로드.
        OCR 완료 후 LLM 로드 전에 호출.
        """
        if self._model is not None:
            del self._model
            self._model = None
        if self._processor is not None:
            del self._processor
            self._processor = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        with self._lock:
            Qwen2VLEngine._instance = None
        logger.info('Qwen2.5-VL 모델 언로드 완료')

    def _run_inference(self, pil_image: Image.Image, prompt: str, max_new_tokens: int) -> str:
        """
        공통 추론 헬퍼. 이미지 + 프롬프트로 텍스트 생성.

        Args:
            pil_image: PIL 이미지 (RGB)
            prompt: 프롬프트 텍스트
            max_new_tokens: 최대 생성 토큰 수

        Returns:
            생성된 텍스트 (strip 처리됨)
        """
        messages = [
            {
                'role': 'user',
                'content': [
                    {'type': 'image', 'image': pil_image},
                    {'type': 'text', 'text': prompt},
                ],
            }
        ]

        text = self._processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = self._processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors='pt',
        ).to(self._device)

        with torch.no_grad():
            generated_ids = self._model.generate(**inputs, max_new_tokens=max_new_tokens)

        generated_ids_trimmed = [
            out_ids[len(in_ids):]
            for in_ids, out_ids in zip(inputs.input_ids, generated_ids, strict=False)
        ]
        return self._processor.batch_decode(
            generated_ids_trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0].strip()

    def _classify_image(self, pil_image: Image.Image) -> ImageType:
        """
        1차 호출: 이미지 유형 분류.
        파싱 실패 또는 불명확한 경우 PHOTO로 폴백.

        Returns:
            ImageType.TABLE / ANATOMY / PHOTO
        """
        raw = self._run_inference(pil_image, _CLASSIFY_PROMPT, max_new_tokens=10).lower()
        logger.info('이미지 분류 결과: %r', raw)

        if 'table' in raw:
            return ImageType.TABLE
        if 'anatomy' in raw:
            return ImageType.ANATOMY
        return ImageType.PHOTO  # photo 또는 파싱 실패 → 폴백

    def _describe_image(self, pil_image: Image.Image, image_type: ImageType) -> str:
        """
        2차 호출: 유형별 프롬프트로 접근성 묘사 텍스트 생성.

        Args:
            pil_image: PIL 이미지 (RGB)
            image_type: 1차 분류 결과 (TABLE / ANATOMY / PHOTO)

        Returns:
            시각장애인을 위한 묘사 텍스트
        """
        prompt = _PROMPT_MAP.get(image_type, _PHOTO_PROMPT)
        return self._run_inference(pil_image, prompt, max_new_tokens=1024)

    def recognize_pil(self, pil_image: Image.Image, prompt: str, max_new_tokens: int = 2048) -> str:
        """
        PIL 이미지와 커스텀 프롬프트로 직접 추론.
        스캔형 PDF 페이지 통합 처리 등 외부에서 프롬프트를 직접 지정할 때 사용.

        Args:
            pil_image: PIL 이미지 (RGB)
            prompt: 사용할 프롬프트
            max_new_tokens: 최대 생성 토큰 수

        Returns:
            생성된 텍스트
        """
        if self._model is None or self._processor is None:
            raise RuntimeError('모델이 언로드된 상태입니다. 새 인스턴스를 생성하세요.')
        return self._run_inference(pil_image, prompt, max_new_tokens)

    def recognize(self, image_bytes: bytes) -> OCRResult:
        """
        이미지 바이트를 받아 Qwen2.5-VL로 처리.

        일반 텍스트 이미지: 기존 OCR 경로 (텍스트 추출).
        표/해부도/사진: 2단계 처리 (분류 → 접근성 묘사 생성).

        Args:
            image_bytes: PNG/JPEG 등 이미지 원본 바이트

        Returns:
            OCRResult: raw_text + alt_text + image_type 포함

        Raises:
            ValueError: 이미지 디코딩 실패 시
            RuntimeError: 모델이 언로드된 상태에서 호출 시
        """
        if self._model is None or self._processor is None:
            raise RuntimeError('모델이 언로드된 상태입니다. 새 인스턴스를 생성하세요.')

        try:
            pil_image = Image.open(BytesIO(image_bytes)).convert('RGB')
        except Exception as e:
            raise ValueError(f'이미지 디코딩 실패: {e}') from e

        # 1차: 유형 분류
        image_type = self._classify_image(pil_image)
        logger.info('이미지 유형: %s', image_type.value)

        if image_type == ImageType.TEXT:
            # 기존 텍스트 추출 경로
            raw_text = self._run_inference(pil_image, _OCR_PROMPT, max_new_tokens=2048)
            logger.info('OCR 완료 (텍스트 추출): 길이=%d', len(raw_text))
            return OCRResult(
                boxes=[OCRBox(text=raw_text, confidence=1.0, bbox=[], source='qwen2.5-vl')],
                engine='Qwen2.5-VL-7B',
                avg_confidence=1.0,
                raw_text=raw_text,
                image_type=ImageType.TEXT,
                alt_text=None,
            )

        # 2차: 접근성 묘사 생성
        alt_text = self._describe_image(pil_image, image_type)
        logger.info('접근성 묘사 완료 (유형=%s): 길이=%d', image_type.value, len(alt_text))

        return OCRResult(
            boxes=[OCRBox(text=alt_text, confidence=1.0, bbox=[], source='qwen2.5-vl')],
            engine='Qwen2.5-VL-7B',
            avg_confidence=1.0,
            raw_text=alt_text,   # 하위 호환: raw_text도 묘사 텍스트로 세팅
            image_type=image_type,
            alt_text=alt_text,
        )
