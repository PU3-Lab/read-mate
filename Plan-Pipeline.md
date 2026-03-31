# ReadMate 파이프라인 구조 설계

## 목표

ReadMate는 이미지 문서, PDF, 녹음 파일을 입력받아
`입력 분기 → 텍스트 추출(OCR/pypdf/STT) → LLM 분석 → TTS 낭독 → UI 제공`까지를
하나의 일관된 작업 흐름으로 처리한다.

이번 설계는 단순 기능 나열이 아니라, 실제 구현 시 바로 사용할 수 있도록 다음 4가지를 기준으로 잡는다.

- 모듈이 어디까지 책임지는지 명확할 것
- 각 단계의 입력/출력 데이터 형태가 명확할 것
- 로컬 우선, 실패 시 API 폴백 전략이 명확할 것
- Streamlit UI와 추론 로직이 느슨하게 결합될 것

---

## 전체 아키텍처

```text
[UI Layer]
Streamlit app / 사용자 입력 / 결과 렌더링
    |
    v
[Pipeline Orchestrator]
작업 실행 순서 제어, 상태 저장, 실패 처리, 폴백 결정
    |
    +--> [Input Service]
    |     파일 타입 판별 / 이미지·PDF·오디오 분기
    |
    +--> [Preprocess Service]        (이미지 경로만)
    |     deskew / denoise / contrast / threshold
    |
    +--> [OCR Service]               (이미지 / 스캔형 PDF)
    |     PaddleOCR -> 신뢰도 검사 -> OCR API 폴백
    |
    +--> [PDF Service]               (텍스트형 PDF)
    |     pypdf 텍스트 추출 -> 스캔형 판별 -> OCR 분기
    |
    +--> [STT Service]               (오디오 파일)
    |     faster-whisper -> 텍스트 변환
    |
    +--> [Text Structuring Service]
    |     라인 병합 / 문단 구성 / 클린 텍스트 생성
    |
    +--> [LLM Service]
    |     요약 / 정리 / 질의응답 (JSON 출력)
    |
    +--> [TTS Service]
    |     XTTS v2 음성 합성 / 프리셋 목소리 선택 / ElevenLabs 폴백
    |
    +--> [Storage/Cache Layer]
          세션 상태 / 임시 파일 / 모델 싱글톤 / 중간 결과 캐시
```

핵심 포인트는 `UI`가 직접 모델을 다루지 않고, `Pipeline Orchestrator`를 통해 단계별 서비스를 호출하는 구조다.

---

## 권장 디렉터리 구조

```text
read-mate/
├── app.py
├── src/
│   ├── core/
│   │   ├── config.py          # 환경변수, 경로, 공통 설정
│   │   ├── exceptions.py      # 사용자 정의 예외
│   │   └── logging.py         # 로깅 설정
│   ├── models/
│   │   ├── schemas.py         # Pipeline 입출력 dataclass
│   │   └── enums.py           # 상태, 폴백 타입, 태스크 enum
│   ├── services/
│   │   ├── input_service.py
│   │   ├── preprocess_service.py
│   │   ├── ocr_service.py
│   │   ├── pdf_service.py     # pypdf + 스캔형 분기
│   │   ├── stt_service.py     # faster-whisper
│   │   ├── text_service.py
│   │   ├── llm_service.py
│   │   └── tts_service.py
│   ├── pipelines/
│   │   └── reading_pipeline.py
│   ├── infra/
│   │   ├── cache.py
│   │   ├── files.py
│   │   └── clients/
│   │       ├── clova_ocr.py
│   │       ├── openai_llm.py
│   │       └── elevenlabs.py
│   └── ui/
│       ├── components.py
│       └── state.py
├── lib/
│   └── utils/
│       └── device.py          # available_device() — 모든 서비스에서 import
├── notebooks/
├── Plan-Pipeline.md
└── pyproject.toml
```

---

## 입력 분기 전략

입력 소스는 4가지이며, 타입에 따라 파이프라인 경로가 달라진다.

```text
입력 파일
  ├── 이미지 (.jpg, .png 등)   → Preprocess → OCR → Text Structuring
  ├── PDF
  │     ├── 텍스트형            → PDF Service (pypdf)
  │     └── 스캔형              → Preprocess → OCR Service
  ├── 오디오 (.mp3, .wav 등)   → STT Service
  └── 사용자 질문 (텍스트/음성) → (음성이면 STT) → LLM QA
```

Input Service의 책임:
- 파일 확장자 및 내용 기반 타입 판별
- PDF 텍스트 추출 가능 여부 판단 (스캔형 여부)
- 이미지 정규화 (RGB, EXIF 회전 반영)
- 각 페이지에 `page_index`, `source_type`, `file_name` 메타데이터 부여

---

## 실행 흐름

### 1. 이미지 문서 처리

1. 이미지 업로드 또는 카메라 촬영
2. 이미지 전처리 (deskew, denoise, CLAHE, adaptive threshold)
3. PaddleOCR 수행 → confidence 기반 품질 검증
4. 기준 미달 시 HDX-005 API 폴백
5. Text Structuring → LLM → TTS

전처리 주의사항:
- 전처리 결과는 OCR용, UI 미리보기는 원본 유지
- 지나친 이진화는 한글 획 손실 가능 → 원본 OCR과 결과 비교 후 선택

### 2. PDF 처리

1. PDF 업로드
2. pypdf로 텍스트 추출 시도
3. 텍스트가 충분하면 → Text Structuring → LLM → TTS
4. 텍스트 없거나 부족하면 (스캔형) → 페이지별 이미지 변환 → OCR 경로

PDF 스캔형 판별 기준 예시:
- 전체 페이지 추출 문자 수 `< 100`
- 이미지 비율이 비정상적으로 높음

### 3. 오디오 파일 처리

1. 오디오 파일 업로드
2. faster-whisper STT → 텍스트 변환
3. Text Structuring → LLM 요약/정리 → TTS

STT 처리 참고사항:
- 긴 녹음은 청크 단위 변환 후 병합
- 언어 자동 감지 또는 한국어 지정

### 4. 질의응답

1. 사용자 질문 입력 (텍스트 또는 음성)
2. 음성 질문이면 STT 처리 먼저
3. 업로드된 자료의 추출 텍스트를 컨텍스트로 LLM에 전달
4. 자료 기반 답변 생성 (JSON)
5. TTS로 답변 읽어주기

---

## LLM 분석

LLM 서비스는 한 번의 호출로 여러 산출물을 JSON으로 반환한다.

핵심 산출물 (MVP):
- `summary` — 핵심 3~5문장 요약
- `key_points` — 핵심 정리 항목
- `qa_answer` — 질의응답 답변

확장 산출물:
- `quiz`
- `study_notes`
- `difficulty_level`

권장 처리 방식:
1. 프롬프트 템플릿 구성
2. 모델 선택 (`Qwen2.5-7B` 기본)
3. JSON 스키마 강제
4. 파싱 실패 시 최대 3회 재시도
5. 여전히 실패하면 최소 결과 포맷으로 degrade

모델 선택 우선순위:

```text
Qwen2.5-7B → Qwen2.5-14B → GPT-5.4-mini
```

---

## TTS 합성

- 대상 텍스트: 요약문, 핵심 정리, 질의응답 답변
- 긴 텍스트는 문장 단위 chunking 후 합성
- 프리셋 목소리 선택 지원
- 실패 시 ElevenLabs Eleven Multilingual v2 폴백

처리 순서:
1. TTS 입력 텍스트 정제
2. XTTS v2 호출 (목소리 프리셋 적용)
3. 임시 WAV 파일 저장
4. UI 오디오 플레이어 연결
5. 실패 시 ElevenLabs 폴백

---

## 파이프라인 오케스트레이션

```python
result = reading_pipeline.run(input_payload)
```

오케스트레이터 책임:
- 입력 타입에 따른 분기 결정
- 단계 실행 순서 제어
- 중간 결과 저장
- 단계별 실패 처리 및 폴백 여부 결정
- UI에 전달할 최종 결과 구성

권장 메서드 구조:

```python
class ReadingPipeline:
    def run(self, payload: InputPayload) -> PipelineResult: ...
    def _run_image_path(self, payload: InputPayload) -> str: ...
    def _run_pdf_path(self, payload: InputPayload) -> str: ...
    def _run_audio_path(self, payload: InputPayload) -> str: ...
    def _run_llm(self, text: str, task: TaskType) -> LLMResult: ...
    def _run_tts(self, text: str, voice_preset: str) -> TTSResult: ...
```

---

## 데이터 계약

### 입력 모델

```python
@dataclass
class InputPayload:
    source_type: str   # camera | upload
    file_type: str     # image | pdf | audio | question
    file_name: str
    content: bytes
    question: str | None = None        # 질의응답용
    voice_preset: str = 'default'      # TTS 목소리 선택
```

### STT 결과 모델

```python
@dataclass
class STTResult:
    text: str
    language: str
    segments: list[dict]
```

### OCR 박스 모델

```python
@dataclass
class OCRBox:
    text: str
    confidence: float
    bbox: list[list[int]]
    source: str   # paddle | clova
```

### LLM 결과 모델

```python
@dataclass
class LLMResult:
    summary: str
    key_points: list[str]
    qa_answer: str | None
    quiz: list[QuizItem] | None
```

### 최종 파이프라인 결과 모델

```python
@dataclass
class PipelineResult:
    extracted_text: str
    llm_result: LLMResult | None
    audio_path: str | None
    ocr_engine: str | None
    stt_engine: str | None
    llm_engine: str
    tts_engine: str
    warnings: list[str]
```

---

## 폴백 전략

### OCR 폴백

```text
PaddleOCR
    -> 품질 기준 통과 시 사용
    -> 품질 기준 미달 시 HDX-005 API
```

폴백 기준:
- 평균 confidence `< 0.75`
- 추출 텍스트 길이 `< 최소 글자 수`
- 한글 비율 비정상적으로 낮음

### LLM 폴백

```text
Qwen2.5-7B
    -> JSON 실패 / 품질 미달 / 시간 초과 시 14B
    -> OOM 또는 성능 문제 시 GPT-5.4-mini
```

### TTS 폴백

```text
XTTS v2
    -> 모델 로드 실패 / 합성 시간 과다 시 ElevenLabs
```

폴백 이력은 `warnings` 또는 `engine_trace` 형태로 반드시 기록.

---

## 모델 로딩 전략

- OCR, LLM, STT, TTS 모델은 lazy load (첫 호출 시 로드, 이후 재사용)
- 디바이스는 반드시 `available_device()` 사용

```python
from src.lib.utils.device import available_device
device = available_device()
```

- dtype: `torch.bfloat16` (CUDA/MPS 공통, CPU는 float32 자동 폴백)
- 직접 device 감지 코드 작성 금지

---

## 상태 관리

권장 `st.session_state` 키:

| 키 | 설명 |
|---|---|
| `input_payload` | 현재 입력 파일 메타정보 |
| `extracted_text` | OCR/pypdf/STT로 추출된 텍스트 |
| `llm_result` | JSON 파싱된 결과 |
| `audio_path` | 생성된 오디오 경로 |
| `voice_preset` | 선택한 TTS 목소리 |
| `pipeline_status` | idle / running / success / failed |
| `warnings` | 폴백, 저품질 OCR 등 경고 |

상태 전이:

```text
idle -> input_ready -> processing -> extract_done -> llm_done -> tts_done -> success
                                          \-> failed
```

---

## 에러 처리

| 단계 | 예상 실패 | 처리 |
|---|---|---|
| 입력 | 지원하지 않는 파일 형식 | UI 메시지 표시 |
| 전처리 | 이미지 변환 실패 | 원본 이미지로 OCR 재시도 |
| PDF | 텍스트 추출 실패 | 스캔형으로 판단 후 OCR 분기 |
| OCR | 텍스트 거의 없음 | 경고 후 API 폴백 |
| STT | 오디오 변환 실패 | 에러 메시지 표시 |
| LLM | JSON 파싱 실패 | 재시도 후 최소 응답 반환 |
| TTS | 모델 로드 실패 | ElevenLabs 폴백 또는 오디오 생략 |

권장 예외 클래스:
- `InputValidationError`
- `OCRQualityError`
- `PDFExtractionError`
- `STTError`
- `LLMGenerationError`
- `TTSGenerationError`
- `PipelineExecutionError`

---

## 관측성과 로그

최소 로그 예시:

```text
[input]      type=pdf file=lecture.pdf pages=12
[pdf]        engine=pypdf chars=4821
[llm]        engine=qwen2.5-7b task=summary retry=0 elapsed=5.12s
[tts]        engine=xtts voice=default elapsed=2.87s

[input]      type=audio file=lecture.mp3
[stt]        engine=faster-whisper lang=ko elapsed=8.43s chars=3201
[llm]        engine=qwen2.5-7b task=summary retry=1 elapsed=6.42s
[tts]        engine=xtts voice=default elapsed=3.14s
```

---

## MVP 우선순위

### 1단계 (핵심)

- 이미지 업로드 → 전처리 → PaddleOCR → Qwen2.5-7B 요약 → Streamlit 렌더링
- PDF 업로드 → pypdf 추출 or OCR 분기 → LLM 요약
- 오디오 업로드 → faster-whisper STT → LLM 정리

### 2단계

- XTTS v2 오디오 생성 + 프리셋 목소리 선택
- 자료 기반 질의응답
- 세션 상태 안정화

### 3단계

- OCR API 폴백 (HDX-005)
- GPT-5.4-mini LLM 폴백
- ElevenLabs TTS 폴백
- 긴 문서 챕터 분리

---

## 최종 권장 구조 요약

```text
UI는 입력/출력만 담당
Pipeline은 입력 타입 분기, 실행 순서, 실패 복구를 담당
Service는 각 단계의 순수 기능을 담당 (OCR/PDF/STT/LLM/TTS)
Model/Schema는 단계 간 계약을 담당
Infra는 외부 API, 캐시, 파일, 디바이스 공통 기능을 담당
```

---

## 바로 다음 구현 순서 제안

1. `src/models/schemas.py` — 데이터 계약 고정
2. `src/core/config.py`, `src/core/exceptions.py`
3. `src/services/input_service.py` — 파일 타입 분기
4. `src/services/preprocess_service.py` — 이미지 전처리
5. `src/services/ocr_service.py` — PaddleOCR 단일 경로
6. `src/services/pdf_service.py` — pypdf + 스캔형 분기
7. `src/services/stt_service.py` — faster-whisper
8. `src/services/llm_service.py` — Qwen2.5-7B JSON 출력
9. `src/services/tts_service.py` — XTTS v2 + 목소리 선택
10. `src/pipelines/reading_pipeline.py` — 전체 오케스트레이션
11. `app.py` + `src/ui/` — Streamlit 화면 연결
