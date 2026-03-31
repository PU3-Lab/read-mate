# ReadMate — CLAUDE.md

## 프로젝트 개요

실물 종이책을 촬영하여 **OCR → LLM 분석 → TTS 낭독**까지 제공하는 Streamlit 기반 학습 보조 도구.

- **문서:** [Notion](https://www.notion.so/ReadMate-3338f00bb4b980f1bdc2ced2825ed8f1) | [Google Docs](https://docs.google.com/document/d/13evEuSCxKVuTBAD8XnT6HVEnLOuqBFVUP8qvo9BUcfE/edit)
- **설계 문서:** `Plan-TechStack.md`, `Plan-Pipeline.md`

---

## 환경

- **OS:** Mac Apple Silicon (MPS 백엔드)
- **패키지 관리:** `uv`
- **Python:** 3.11+
- **가상환경:** `uv sync`으로 설치

### ⚠️ 필수 규칙

- MPS에서 fp16 NaN 오버플로 발생 → **bf16 필수**
- CUDA 전용 툴 사용 불가 (Trellis 등)
- torch/torchvision/torchaudio는 Mac에서 PyPI 기본값 사용 (pytorch-gpu 인덱스는 Win/Linux 전용)

---

## 기술 스택

| 역할 | 로컬 (기본) | API 폴백 (성능 미달 시) |
|------|-----------|----------------------|
| **UI** | Streamlit | — |
| **OCR** | PaddleOCR | HDX-005 (네이버 클로바) |
| **OCR 보조** | TrOCR | — |
| **LLM** | Qwen2.5-7B-Instruct | GPT-5.4-mini |
| **LLM 확장** | Qwen2.5-14B-Instruct | — |
| **TTS** | XTTS v2 (`coqui-tts`) | ElevenLabs Eleven Multilingual v2 |

> **기본 방침:** 로컬 우선 → 성능 미달 시 API 전환

### 제외된 모델

- **MeloTTS:** `transformers==4.27.4` 고정으로 `transformers>=5.3.0`과 버전 충돌 → 제외

---

## 파이프라인 구조

```
입력 (카메라/파일) → 전처리 (OpenCV) → OCR (PaddleOCR)
→ LLM 분석 (Qwen2.5) → TTS (XTTS v2) → UI 출력 (Streamlit)
```

### 모듈 역할 (`src/`)

| 파일 | 역할 |
|------|------|
| `app.py` | Streamlit 진입점 |
| `src/input.py` | 입력 수신 및 이미지/PDF 분기 |
| `src/preprocess.py` | OpenCV 전처리 (기울기 보정, 노이즈 제거) |
| `src/ocr.py` | PaddleOCR + TrOCR 보조, 텍스트 병합 |
| `src/llm.py` | Qwen2.5 추론, JSON 출력 (요약/퀴즈/키워드) |
| `src/tts.py` | XTTS v2 음성 합성, .wav 출력 |
| `src/ui.py` | Streamlit UI 컴포넌트 |

---

## 코드 작성 규칙

- 모델 로드 시 항상 MPS 우선, CPU 폴백
  ```python
  device = "mps" if torch.backends.mps.is_available() else "cpu"
  ```
- 모델 dtype은 항상 `torch.bfloat16`
- LLM 출력은 JSON 포맷으로 강제 (재시도 최대 3회)
- API 키는 `.env`에서 `python-dotenv`로 관리
- OCR 입력 타입 분기: 이미지 → PaddleOCR `/general` / PDF → `/document`
- 린터: `ruff` (설정은 `pyproject.toml` 참고)

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
- MPS 관련 에러는 bf16 / CPU 폴백 순서로 확인
- 패키지 충돌은 `pyproject.toml` 직접 수정

### 코드 리뷰
- 성능, 가독성, MPS 호환성 세 가지 기준으로 검토
- 문제 발견 시 수정안 바로 제시

### 질문하는 경우 (예외)
- 기술 스택 자체를 바꾸는 결정
- 파이프라인 구조를 크게 변경하는 경우

---

## MVP 체크리스트

- [ ] 환경 구축 및 Qwen2.5-7B 실행 확인
- [ ] PaddleOCR 책 페이지 인식 테스트
- [ ] LLM 프롬프트 튜닝 (JSON 포맷 출력)
- [ ] Streamlit 전체 파이프라인 연결
- [ ] 로컬 리소스 최적화
