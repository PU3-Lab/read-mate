# GEMINI.md - ReadMate Project Instructions

이 파일은 Gemini CLI가 이 프로젝트에서 준수해야 할 핵심 지침과 프로젝트 컨벤션을 담고 있습니다. 이 지침은 시스템 프롬프트보다 우선하며, 모든 작업 시 최우선적으로 고려되어야 합니다.

## 1. 프로젝트 개요 및 기술 스택
- **프로젝트 명:** ReadMate (Streamlit 기반 학습 보조 도구)
- **주요 기능:** 이미지/PDF/오디오 텍스트 추출, 요약, 질의응답, TTS(음성 변환)
- **패키지 관리:** `uv`
- **핵심 라이브러리:**
  - OCR: PaddleOCR : 변경 될수 있음
  - STT: faster-whisper
  - LLM: Qwen2.5-7B-Instruct (Local), GPT-4o-mini (API Fallback)
  - TTS: zonos
  - UI: Streamlit

## 2. 핵심 개발 규칙 (Mandatory)
- **디바이스 감지:** 반드시 `src/lib/utils/device.py`의 `available_device()`를 사용해야 합니다. 직접 감지 로직을 작성하지 마십시오.
- **데이터 타입 (dtype):** 모델 로드 시 항상 `torch.bfloat16`을 사용합니다. (MPS/CUDA 공통, CPU는 자동 폴백 처리)
- **모델 로딩:** 싱글톤(Singleton) 패턴을 적용하여 매 호출마다 모델이 재로드되지 않도록 합니다.
- **LLM 출력:** 반드시 JSON 포맷으로 강제하며, 파싱 실패 시 최대 3회 재시도합니다.
- **보안:** API 키는 반드시 `.env` 파일과 `python-dotenv`를 통해 관리하며, 코드에 직접 노출하거나 커밋하지 않습니다.
- **언어:** 커뮤니케이션 및 코드 내 docstring은 한국어를 사용합니다.

## 3. 코드 스타일 및 품질 지침
- **린터 및 포맷터:** `ruff`를 사용합니다. (`pyproject.toml` 설정 준수)
- **타입 힌트:** 모든 함수와 메서드에 타입 힌트 작성이 필수입니다.
- **문서화:** 모든 함수에 docstring을 작성합니다. (한국어 권장)
- **디렉토리 구조:** 새로운 소스 코드는 `src/` 하위의 적절한 모듈에 위치시킵니다.
- 함수안에서 import 하지말것
- 구현부는 별도 파일로 같은 파일에 클래스 한개이상 넣지 말것
- 디바이스 감지는 **직접 작성 금지**, 반드시 `src/lib/utils/device.py`의 `available_device()` 사용
  ```python
  from src.lib.utils.device import available_device
  device = available_device()
  ```
- path는 lib.utils.path안에 함수 사용 및 추가
- import 시 src. 사용금지

## 4. Gemini CLI 작업 프로세스
- **Research -> Strategy -> Execution:** 작업을 시작하기 전 항상 관련 파일을 읽고 이해한 뒤, 전략을 세우고 실행합니다.
- **Explain Before Acting:** 도구를 실행하기 전, 실행 의도와 전략을 짧고 명확하게 설명합니다.
- **Validation:** 모든 변경 사항은 테스트나 실행 확인을 통해 반드시 검증해야 합니다. 검증되지 않은 변경은 완료로 간주하지 않습니다.
- **Surgical Updates:** 코드 수정 시 기존 스타일과 구조를 존중하며, 필요한 부분만 정확하게 수정합니다.

## 5. 플랫폼별 주의사항
- **Mac (Apple Silicon):** `fp16` 사용 시 NaN 오버플로가 발생할 수 있으므로 반드시 `bf16`을 사용합니다.
- **Windows/Linux:** CUDA 환경에서도 일관성을 위해 `bf16`을 권장합니다.
- **CUDA 전용 툴:** Mac 환경에서는 CUDA 전용 도구를 사용하지 않도록 주의합니다.

---
*이 지침은 프로젝트 진행 상황에 따라 업데이트될 수 있습니다.*
