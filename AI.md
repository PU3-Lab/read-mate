# ReadMate — 공통 AI 지침

이 파일은 모든 AI 도구(Claude, Gemini, Codex 등)가 공통으로 준수해야 할 프로젝트 규칙입니다.
각 AI별 설정 파일(`.claude/CLAUDE.md`, `.gemini/GEMINI.md`, `.codex/AGENTS.md`)은 이 파일을 기본 규칙으로 참조합니다.

---

## 프로젝트 개요

이미지 문서, PDF, 녹음 파일을 입력받아 내용을 추출하고, **요약·정리·질의응답**을 제공하는 Streamlit 기반 학습 보조 도구.

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
| **OCR** | Qwen2.5-VL-7B (4-bit 양자화) | HDX-005 (네이버 클로바) |
| **PDF 추출** | pypdf (텍스트형) + Qwen2.5-VL (스캔형) | — |
| **STT** | faster-whisper | — |
| **LLM** | Gemma4-E4B-it | GPT-5.4-mini |
| **LLM 확장** | Gemma4-26B-A4B-it | — |

> **기본 방침:** 로컬 우선 → 성능 미달 시 API 전환

### 제외된 모델

- **MeloTTS:** `transformers==4.27.4` 고정으로 `transformers>=5.3.0`과 버전 충돌 → 제외
- **EasyOCR / PaddleOCR:** Qwen2.5-VL(VLM 기반 OCR)로 교체 — 한국어 인식률 및 복잡한 레이아웃 처리 우위
- **XTTS v2 (coqui-tts):** `coqui-tts` 패키지 버전 충돌로 제외

---

## 파이프라인 구조

```
[문서 이미지]  → 이미지 업로드 → OCR (Qwen2.5-VL) → 텍스트 정리 → LLM 요약
[PDF]         → PDF 업로드   → 텍스트 추출(pypdf) 또는 OCR → 요약/정리
[오디오]       → 파일 업로드  → STT (faster-whisper) → 요약/정리
[질의응답]     → 질문 입력    → LLM (Qwen2.5) → 자료 기반 답변
```

### 모듈 역할 (`src/`)

| 파일 | 역할 |
|------|------|
| `app.py` | Streamlit 진입점 |
| `src/input.py` | 입력 수신 및 이미지/PDF/오디오 분기 |
| `src/preprocess.py` | 이미지 전처리 (기울기 보정, 노이즈 제거) |
| `src/ocr.py` | Qwen2.5-VL 텍스트 인식, 스캔형 PDF OCR |
| `src/pdf.py` | pypdf 텍스트 추출, 스캔형 판별 후 OCR 분기 |
| `src/stt.py` | faster-whisper 음성→텍스트 변환 |
| `src/llm.py` | Qwen2.5 추론, 요약/정리/질의응답 |
| `src/ui.py` | Streamlit UI 컴포넌트 |

---

## 코드 작성 규칙

- 모델 dtype은 항상 `torch.bfloat16` (CUDA/MPS 공통, CPU는 float32 자동 폴백)
- LLM 출력은 JSON 포맷으로 강제 (재시도 최대 3회)
- API 키는 `.env`에서 `python-dotenv`로 관리
- PDF 분기: 텍스트 추출 가능 → pypdf / 스캔형 → Qwen2.5-VL OCR
- OCR/LLM 메모리 전략: OCR 완료 후 VL 모델 언로드 → LLM 로드 (`Qwen2VLEngine.unload()`)
- 린터: `ruff` (설정은 `pyproject.toml` 참고)
- 코드 수정 후 반드시 `ruff check --fix <대상 경로>` 먼저 실행
- `ruff check --fix` 후 반드시 `ruff check <대상 경로>`로 최종 확인
- 기본 범위는 전체 저장소가 아니라 **이번에 수정한 파일 또는 모듈만** 대상으로 실행
- 함수 안에서 import 하지 말것
- 구현부는 별도 파일로, 같은 파일에 클래스 하나 이상 넣지 말것
- import 시 `src.` 사용 금지
- 모델 로드는 싱글톤 패턴 (매 호출마다 재로드 금지)
- 모든 함수에 docstring 작성 (한국어 가능)
- 타입 힌트 필수
- 새 파일은 `src/` 하위에 생성
- 멀티 플랫폼 지원

### 디바이스 감지 — `lib.utils.device`

직접 감지 로직 작성 금지. 반드시 `available_device()`를 사용합니다.

```python
from lib.utils.device import available_device
device = available_device()  # 'cuda' | 'mps' | 'cpu'
```

### 경로 관리 — `lib.utils.path`

하드코딩된 경로 사용 금지. 반드시 아래 함수를 사용하고, 새 경로가 필요하면 이 모듈에 추가합니다.

| 함수 | 반환 경로 | 용도 |
|------|-----------|------|
| `model_path(file_name?)` | `data/models/` | 모델 파일 저장/로드 |
| `data_path()` | `data/` | 데이터 루트 |
| `tmp_path()` | `data/tmp/` | 임시 파일 (처리 중 중간 결과) |
| `images_path()` | `data/images/` | 이미지 파일 |
| `voices_path()` | `data/voices/` | 음성 파일 |
| `keys_path()` | `keys/` | 암호화 키 파일 |

```python
from lib.utils.path import model_path, tmp_path, images_path

model = model_path('qwen2vl.bin')   # data/models/qwen2vl.bin
out   = tmp_path() / 'ocr_out.txt'  # data/tmp/ocr_out.txt
```

---

## 작업 방식

### 기본 원칙
- 코드 작성 / 디버깅 / 리뷰는 **묻지 않고 바로 진행**
- 작업 전 관련 파일 먼저 읽고 파악한 뒤 시작
- 한 번에 하나의 모듈 완성 후 다음으로 이동
- 완료 후 **간단한 요약 + 다음 단계 제안**으로 마무리

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
- 작업 완료 후 커밋 전 반드시 사용자 승인 후 진행 (md 파일만 변경된 경우 제외)
- 커밋 승인 요청 전 동작 테스트 확인 필수
- `git push` 전 반드시 사용자 승인 후 진행
