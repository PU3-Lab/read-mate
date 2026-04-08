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
from models.schemas import OCRBox, OCRResult
from services.base import BaseOCR

logger = logging.getLogger(__name__)

_MODEL_ID = 'Qwen/Qwen2.5-VL-7B-Instruct'

# 기존 텍스트 추출 프롬프트
_OCR_PROMPT = (
    '이 이미지에서 모든 텍스트를 추출하세요. 텍스트만 출력하고 다른 설명은 하지 마세요.'
)

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
        이미지 바이트를 받아 Qwen2.5-VL로 텍스트 추출.

        Args:
            image_bytes: PNG/JPEG 등 이미지 원본 바이트

        Returns:
            OCRResult: 추출된 텍스트

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

        raw_text = self._run_inference(pil_image, _OCR_PROMPT, max_new_tokens=2048)
        logger.info('OCR 완료: 길이=%d', len(raw_text))

        return OCRResult(
            boxes=[OCRBox(text=raw_text, confidence=1.0, bbox=[], source='qwen2.5-vl')],
            engine='Qwen2.5-VL-7B',
            avg_confidence=1.0,
            raw_text=raw_text,
        )
