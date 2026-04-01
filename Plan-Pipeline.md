# ReadMate 파이프라인 구조 설계

## 목표

ReadMate는 이미지 문서, PDF, 녹음 파일을 입력받아
`입력 분기 → 텍스트 추출(OCR/pypdf/STT) → LLM 분석 → TTS 낭독 → UI 제공`까지를
하나의 일관된 작업 흐름으로 처리한다.

설계 기준:

- 모듈이 어디까지 책임지는지 명확할 것
- 각 단계의 입력/출력 데이터 형태가 명확할 것
- 로컬 우선, 실패 시 API 폴백 전략이 명확할 것
- Streamlit UI와 추론 로직이 느슨하게 결합될 것
- 모델 교체 시 파이프라인 코드를 건드리지 않을 것 (ABC + DI)

---

## OOP 설계 원칙

각 서비스는 ABC(추상 기반 클래스)로 인터페이스를 정의하고,
구체적인 모델 구현체를 `ReadingPipeline` 생성자에서 주입한다.

```
ABC 인터페이스          구현체 (로컬)         구현체 (API 폴백)
─────────────────────────────────────────────────────────────
BaseOCR          →  PaddleOCREngine     /  ClovaOCREngine
BasePDF          →  PyPDFEngine         (내부에서 OCR 분기)
BaseSTT          →  FasterWhisperEngine
BaseLLM          →  QwenLLM             /  OpenAILLM
BaseTTS          →  XTTSEngine          /  ElevenLabsTTS
```

모델 교체 예시:

```python
# PaddleOCR → Clova로 교체할 때 파이프라인 코드는 그대로
pipeline = ReadingPipeline(
    ocr=ClovaOCREngine(),
    pdf=PyPDFEngine(ocr_fallback=ClovaOCREngine()),
    stt=FasterWhisperEngine(),
    llm=QwenLLM(),
    tts=XTTSEngine(),
)
```

---

## 전체 아키텍처

```text
[UI Layer]
Streamlit app / 사용자 입력 / 결과 렌더링
    |
    v
[ReadingPipeline]  ← 엔진들을 생성자에서 주입받음
    |
    +--> [BaseOCR]         이미지 → 텍스트 (PaddleOCR / ClovaOCR)
    |
    +--> [BasePDF]         PDF → 텍스트 (pypdf + OCR 분기)
    |
    +--> [BaseSTT]         오디오 → 텍스트 (faster-whisper)
    |
    +--> [BaseLLM]         텍스트 → 요약/QA JSON (Qwen2.5 / GPT)
    |
    +--> [BaseTTS]         텍스트 → 음성 (XTTS v2 / ElevenLabs)
    |
    +--> [Cache / Storage] 모델 싱글톤, 임시 파일, 세션 상태
```

---

## 디렉터리 구조

```text
read-mate/
├── app.py
├── src/
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py          # 입출력 dataclass / Enum 전체
│   ├── services/
│   │   ├── __init__.py
│   │   ├── base.py             # ABC: BaseOCR, BasePDF, BaseSTT, BaseLLM, BaseTTS
│   │   ├── ocr_service.py      # PaddleOCREngine, ClovaOCREngine
│   │   ├── pdf_service.py      # PyPDFEngine (OCR 분기 포함)
│   │   ├── stt_service.py      # FasterWhisperEngine
│   │   ├── llm_service.py      # QwenLLM, OpenAILLM
│   │   └── tts_service.py      # XTTSEngine, ElevenLabsTTS
│   ├── pipelines/
│   │   ├── __init__.py
│   │   └── reading_pipeline.py # ReadingPipeline 오케스트레이터
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py           # 환경변수, 경로, 공통 설정
│   │   └── exceptions.py       # 사용자 정의 예외
│   └── lib/
│       └── utils/
│           └── device.py       # available_device() — 직접 작성 금지
├── Plan-Pipeline.md
├── Plan-TechStack.md
├── CLAUDE.md
└── pyproject.toml
```

---

## 데이터 계약 (`src/models/schemas.py`)

단계 간 전달되는 모든 데이터는 여기서 정의한다.

### Enum

```python
class InputType(Enum):
    IMAGE = 'image'
    PDF = 'pdf'
    AUDIO = 'audio'
    QUESTION = 'question'

class TaskType(Enum):
    SUMMARIZE = 'summarize'
    QA = 'qa'

class PipelineStatus(Enum):
    IDLE = 'idle'
    RUNNING = 'running'
    SUCCESS = 'success'
    FAILED = 'failed'
```

### 주요 데이터 클래스

```python
@dataclass
class InputPayload:
    input_type: InputType
    file_name: str
    content: bytes
    question: str | None = None
    voice_preset: str = 'default'

@dataclass
class OCRResult:
    boxes: list[OCRBox]
    engine: str
    avg_confidence: float
    raw_text: str

@dataclass
class PDFResult:
    text: str
    page_count: int
    is_scanned: bool

@dataclass
class STTResult:
    text: str
    language: str
    segments: list[STTSegment]
    engine: str

@dataclass
class LLMResult:
    summary: str
    key_points: list[str]
    qa_answer: str | None = None
    quiz: list[QuizItem] | None = None
    engine: str = ''

@dataclass
class TTSResult:
    audio_path: str
    voice_preset: str
    engine: str
    duration_sec: float

@dataclass
class PipelineResult:
    extracted_text: str
    llm_result: LLMResult | None = None
    tts_result: TTSResult | None = None
    ocr_engine: str | None = None
    stt_engine: str | None = None
    status: PipelineStatus = PipelineStatus.SUCCESS
    warnings: list[str] = field(default_factory=list)
```

---

## ABC 인터페이스 (`src/services/base.py`)

```python
class BaseOCR(ABC):
    @abstractmethod
    def recognize(self, image_bytes: bytes) -> OCRResult: ...

class BasePDF(ABC):
    @abstractmethod
    def extract(self, pdf_bytes: bytes) -> PDFResult: ...

class BaseSTT(ABC):
    @abstractmethod
    def transcribe(self, audio_bytes: bytes) -> STTResult: ...

class BaseLLM(ABC):
    @abstractmethod
    def generate(self, text: str, task: TaskType, question: str | None = None) -> LLMResult: ...

class BaseTTS(ABC):
    @abstractmethod
    def synthesize(self, text: str, voice_preset: str = 'default') -> TTSResult: ...

    @abstractmethod
    def list_presets(self) -> list[str]: ...
```

---

## 파이프라인 오케스트레이터 (`src/pipelines/reading_pipeline.py`)

```python
class ReadingPipeline:
    def __init__(self, ocr: BaseOCR, pdf: BasePDF, stt: BaseSTT, llm: BaseLLM, tts: BaseTTS):
        ...

    def run(self, payload: InputPayload) -> PipelineResult:
        # 1. 입력 타입 분기 → 텍스트 추출
        # 2. LLM 분석 (SUMMARIZE or QA)
        # 3. TTS 합성 (실패해도 파이프라인 계속)
        ...
```

### 입력 타입별 분기

```text
InputType.IMAGE    → _run_image()    → BaseOCR.recognize()
InputType.PDF      → _run_pdf()      → BasePDF.extract() (스캔형이면 내부에서 OCR)
InputType.AUDIO    → _run_audio()    → BaseSTT.transcribe()
InputType.QUESTION → 질문 텍스트 그대로 → LLM QA
```

### TTS 처리 원칙

- QA 태스크 → `qa_answer` 읽어주기
- 요약 태스크 → `summary` 읽어주기
- TTS 실패 시 `warnings`에 기록하고 파이프라인은 계속 진행

---

## 폴백 전략

### OCR

```text
PaddleOCR
  → avg_confidence < 0.75 또는 추출 텍스트 부족 시 ClovaOCR (HDX-005)
```

### PDF

```text
pypdf 텍스트 추출
  → 추출 문자 수 부족 (스캔형 판별) 시 OCR 경로로 내부 분기
```

### LLM

```text
Qwen2.5-7B
  → JSON 파싱 실패 / 품질 미달 → 최대 3회 재시도
  → OOM / 시간 초과 → Qwen2.5-14B
  → 여전히 실패 → GPT-5.4-mini
```

### TTS

```text
XTTS v2
  → 모델 로드 실패 / 합성 과다 → ElevenLabs Eleven Multilingual v2
```

---

## 모델 로딩 전략

- 모든 엔진은 **싱글톤 lazy load** (첫 호출 시 로드, 이후 재사용)
- 디바이스는 반드시 `available_device()` 사용

```python
from lib.utils.device import available_device

device = available_device()   # cuda | mps | cpu
```

- dtype: `torch.bfloat16` (CUDA/MPS 공통, CPU는 float32 자동 폴백)
- 직접 device 감지 코드 작성 금지

---

## 에러 처리

| 단계 | 예상 실패 | 처리 |
|---|---|---|
| 입력 | 지원하지 않는 파일 형식 | UI 메시지 표시 |
| 전처리 | 이미지 변환 실패 | 원본으로 OCR 재시도 |
| PDF | 텍스트 추출 실패 | 스캔형 판단 후 OCR 분기 |
| OCR | 텍스트 거의 없음 | 경고 후 ClovaOCR 폴백 |
| STT | 오디오 변환 실패 | 에러 메시지 표시 |
| LLM | JSON 파싱 실패 | 재시도 3회 후 최소 응답 |
| TTS | 모델 로드 실패 | ElevenLabs 폴백 또는 오디오 생략 |

권장 예외 클래스 (`src/core/exceptions.py`):

- `InputValidationError`
- `OCRQualityError`
- `PDFExtractionError`
- `STTError`
- `LLMGenerationError`
- `TTSGenerationError`
- `PipelineExecutionError`

---

## 상태 관리 (`st.session_state`)

| 키 | 설명 |
|---|---|
| `input_payload` | 현재 입력 파일 메타정보 |
| `extracted_text` | OCR / pypdf / STT 추출 텍스트 |
| `llm_result` | JSON 파싱된 LLM 결과 |
| `audio_path` | 생성된 오디오 경로 |
| `voice_preset` | 선택한 TTS 목소리 |
| `pipeline_status` | idle / running / success / failed |
| `warnings` | 폴백, 저품질 경고 등 |

상태 전이:

```text
idle → input_ready → processing → extract_done → llm_done → tts_done → success
                                       └→ failed
```

---

## 구현 로그

### 완료

- [x] `src/models/schemas.py` — 입출력 dataclass / Enum
- [x] `src/services/base.py` — ABC 인터페이스 (BaseOCR, BasePDF, BaseSTT, BaseLLM, BaseTTS)
- [x] `src/pipelines/reading_pipeline.py` — 오케스트레이터 (DI, 입력 분기, 폴백 로깅)

### 다음 구현 순서

1. `src/core/exceptions.py` — 사용자 정의 예외
2. `src/core/config.py` — 환경변수, 경로 설정
3. `src/services/ocr_service.py` — PaddleOCREngine
4. `src/services/pdf_service.py` — PyPDFEngine
5. `src/services/stt_service.py` — FasterWhisperEngine
6. `src/services/llm_service.py` — QwenLLM
7. `src/services/tts_service.py` — XTTSEngine
8. `app.py` + UI 연결
