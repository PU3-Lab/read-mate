# ReadMate — AGENTS.md

## 프로젝트 개요

이미지 문서, PDF, 녹음 파일을 입력받아 내용을 추출하고, **요약·정리·질의응답·음성 읽어주기**를 제공하는 Streamlit 기반 학습 보조 도구.

- **문서:** [Notion](https://www.notion.so/ReadMate-3338f00bb4b980f1bdc2ced2825ed8f1) | [Google Docs](https://docs.google.com/document/d/13evEuSCxKVuTBAD8XnT6HVEnLOuqBFVUP8qvo9BUcfE/edit)
- **설계 문서:** `Plan-TechStack.md`, `Plan-Pipeline.md`

---

## 환경

- **OS:** Mac Apple Silicon / Windows / Linux
- **패키지 관리:** `uv`
- **Python:** 3.11+
- **가상환경:** `uv sync`으로 설치

| OS | 백엔드 | torch 인덱스 |
|----|--------|-------------|
| Mac Apple Silicon | MPS | PyPI 기본값 |
| Windows | CUDA (cu126) | pytorch-gpu |
| Linux | CUDA (cu126) | pytorch-gpu |

### ⚠️ 필수 규칙

- **Mac MPS:** fp16 NaN 오버플로 발생 → **bf16 필수**
- **Windows/Linux CUDA:** fp16 사용 가능, bf16 권장 (일관성)
- torch/torchvision/torchaudio는 Mac에서 PyPI 기본값, Win/Linux는 pytorch-gpu 인덱스 사용
- CUDA 전용 툴 (Trellis 등)은 Mac에서 사용 불가

---

## 기술 스택

| 역할 | 로컬 (기본) | API 폴백 (성능 미달 시) |
|------|-----------|----------------------|
| **UI** | Streamlit | — |
| **OCR** | PaddleOCR | HDX-005 (네이버 클로바) |
| **PDF 추출** | pypdf (텍스트형) + PaddleOCR (스캔형) | — |
| **STT** | faster-whisper | — |
| **LLM** | Qwen2.5-7B-Instruct | GPT-5.4-mini |
| **LLM 확장** | Qwen2.5-14B-Instruct | — |
| **TTS** | XTTS v2 (`coqui-tts`) | ElevenLabs Eleven Multilingual v2 |

> **기본 방침:** 로컬 우선 → 성능 미달 시 API 전환

### 제외된 모델

- **MeloTTS:** `transformers==4.27.4` 고정으로 `transformers>=5.3.0`과 버전 충돌 → 제외
- **TrOCR:** 최신 기획에서 제외, PaddleOCR 단독 사용

---

## 파이프라인 구조

```
[문서 이미지]  → 이미지 업로드 → OCR (PaddleOCR) → 텍스트 정리 → TTS
[PDF]         → PDF 업로드   → 텍스트 추출(pypdf) 또는 OCR → 요약/정리 → TTS
[오디오]       → 파일 업로드  → STT (faster-whisper) → 요약/정리 → TTS
[질의응답]     → 질문 입력    → LLM (Qwen2.5) → 자료 기반 답변 → TTS
```

### 모듈 역할 (`src/`)

| 파일 | 역할 |
|------|------|
| `app.py` | Streamlit 진입점 |
| `src/input.py` | 입력 수신 및 이미지/PDF/오디오 분기 |
| `src/preprocess.py` | OpenCV 전처리 (기울기 보정, 노이즈 제거) |
| `src/ocr.py` | PaddleOCR 텍스트 인식, 스캔형 PDF OCR |
| `src/pdf.py` | pypdf 텍스트 추출, 스캔형 판별 후 OCR 분기 |
| `src/stt.py` | faster-whisper 음성→텍스트 변환 |
| `src/llm.py` | Qwen2.5 추론, 요약/정리/질의응답 |
| `src/tts.py` | XTTS v2 음성 합성, 프리셋 목소리 선택 |
| `src/ui.py` | Streamlit UI 컴포넌트 |

---

## 코드 작성 규칙

- 디바이스 감지는 **직접 작성 금지**, 반드시 `src/lib/utils/device.py`의 `available_device()` 사용
  ```python
  from src.lib.utils.device import available_device
  device = available_device()
  ```
- 모델 dtype은 항상 `torch.bfloat16` (CUDA/MPS 공통, CPU는 float32 자동 폴백)
- LLM 출력은 JSON 포맷으로 강제 (재시도 최대 3회)
- API 키는 `.env`에서 `python-dotenv`로 관리
- OCR 입력 타입 분기: 이미지 → PaddleOCR `/general` / PDF → `/document`
- PDF 분기: 텍스트 추출 가능 → pypdf / 스캔형 → PaddleOCR
- 코드 작성 시 현재 `pyproject.toml`의 `ruff` 규칙을 우선 준수하며, 세부 기준 변경 시에도 `pyproject.toml`을 기준으로 맞춘다
- `ruff` 스타일 기준: 최대 줄 길이 `88`, 문자열은 기본 `single quote`, import 정렬은 `ruff` 기준 유지
- `ruff` 린트 적용 범위: `E`, `F`, `I`, `B`, `C4`, `UP`, `N`, `SIM`
- `ruff` 현재 무시 규칙: `E501`, `N803`, `N812`, `E401`, `N806`, `N816`
- `ruff` 전 파일 예외: `ANN`, `INP001`
- `ruff`가 `ANN`을 강제하지 않더라도, 이 프로젝트에서는 타입 힌트와 docstring 작성을 계속 필수로 본다

---

## 작업 방식

### 기본 원칙
- 코드 작성 / 디버깅 / 리뷰는 **묻지 않고 바로 진행**
- 작업 전 관련 파일 먼저 읽고 파악한 뒤 시작
- 한 번에 하나의 모듈 완성 후 다음으로 이동
- 완료 후 **간단한 요약 + 다음 단계 제안**으로 마무리

### 코드 작성
- 새 파일은 `src/` 하위에 생성
- 모든 함수에 docstring 작성 (한국어 가능)
- 타입 힌트 필수
- 모델 로드는 싱글톤 패턴 (매 호출마다 재로드 금지)

### 디버깅
- 에러 발생 시 원인 분석 → 수정 → 재확인까지 한 번에 처리
- 디바이스 관련 에러: CUDA → MPS → CPU 폴백 순서로 확인 / bf16 → float32 dtype 폴백
- 패키지 충돌은 `pyproject.toml` 직접 수정

### 코드 리뷰
- 성능, 가독성, 크로스플랫폼 호환성 세 가지 기준으로 검토
- 플랫폼별 체크: Mac(MPS/bf16), Win/Linux(CUDA/bf16), CPU 폴백
- 문제 발견 시 수정안 바로 제시

### 질문하는 경우 (예외)
- 기술 스택 자체를 바꾸는 결정
- 파이프라인 구조를 크게 변경하는 경우

---

## MVP 체크리스트

- [ ] 환경 구축 및 Qwen2.5-7B 실행 확인
- [ ] PaddleOCR 문서 이미지 인식 테스트
- [ ] PDF 텍스트 추출 및 요약 (pypdf + OCR 분기)
- [ ] faster-whisper STT 오디오 변환 테스트
- [ ] LLM 프롬프트 튜닝 (요약/정리/질의응답 JSON 출력)
- [ ] XTTS v2 프리셋 목소리 선택 기능
- [ ] Streamlit 전체 파이프라인 연결
- [ ] 로컬 리소스 최적화
