# 🔧 ReadMate 파이프라인 설계

---

## 전체 흐름

```
[사용자 입력]
    │
    ▼
[Step 1] 입력 수신 (Streamlit UI)
    │  카메라 촬영 or 파일 업로드 (이미지/PDF)
    ▼
[Step 2] 전처리 (OpenCV)
    │  기울기 보정 → 노이즈 제거 → 대비 강화
    ▼
[Step 3] OCR (PaddleOCR)
    │  텍스트 + 좌표 + 신뢰도 추출
    │  저신뢰도 구간 → TrOCR 보조 재인식
    │  파편 텍스트 → 문단 병합
    ▼
[Step 4] LLM 분석 (Qwen2.5-7B-Instruct)
    │  요약 / 퀴즈 생성 / 쉬운 설명 / 키워드 추출
    │  출력 포맷: JSON
    ▼
[Step 5] TTS 합성 (XTTS v2)
    │  요약문 → 한국어 음성 파일 (.wav)
    ▼
[Step 6] UI 출력 (Streamlit)
    │  요약 / 퀴즈 / 오디오 플레이어 / 키워드
    └─ st.session_state로 상태 관리
```

---

## Step 1 — 입력 수신

**담당 모듈:** `src/input.py`

| 항목 | 내용 |
|------|------|
| 입력 방식 | `st.camera_input()` 또는 `st.file_uploader()` |
| 지원 포맷 | JPG, PNG (이미지), PDF |
| 출력 | PIL Image 객체 또는 PDF bytes |

```
입력 타입 분기
├── 이미지 (JPG/PNG) → PIL Image → Step 2
└── PDF             → 페이지별 이미지 변환 (pdf2image) → Step 2
```

---

## Step 2 — 전처리

**담당 모듈:** `src/preprocess.py`

| 처리 순서 | 기법 | 목적 |
|----------|------|------|
| 1 | 그레이스케일 변환 | OCR 인식률 향상 |
| 2 | 기울기 보정 (deskew) | 촬영 각도 보정 |
| 3 | 노이즈 제거 (Gaussian blur) | 잡음 제거 |
| 4 | 대비 강화 (CLAHE) | 흐린 텍스트 선명화 |
| 5 | 이진화 (Adaptive Threshold) | 배경/텍스트 분리 |

- **입력:** PIL Image
- **출력:** 전처리된 numpy array

---

## Step 3 — OCR

**담당 모듈:** `src/ocr.py`

```
PaddleOCR 추출
    │  출력: [(text, bbox, confidence), ...]
    ▼
신뢰도 필터링 (threshold: 0.8)
    ├── confidence >= 0.8 → 그대로 사용
    └── confidence < 0.8  → TrOCR 재인식
    ▼
파편 텍스트 병합
    │  bbox Y좌표 기반으로 같은 줄 판단 → 문단 구성
    ▼
출력: 정제된 텍스트 (str)
```

> ⚠️ **API 폴백 (HDX-005):** PaddleOCR 전체 신뢰도 낮을 시 Naver HyperCLOVA OCR로 전환
> - 이미지 파일 → `/general` 엔드포인트
> - PDF 파일 → `/document` 엔드포인트

---

## Step 4 — LLM 분석

**담당 모듈:** `src/llm.py`

**모델 로드**
```python
# MPS(Apple Silicon) 우선, CPU 폴백
device = "mps" if torch.backends.mps.is_available() else "cpu"
```

**프롬프트 태스크 및 출력 포맷 (JSON)**

```json
{
  "summary": "핵심 내용 3~5문장 요약",
  "quiz": [
    {
      "question": "문제",
      "options": ["①", "②", "③", "④"],
      "answer": 0
    }
  ],
  "keywords": ["키워드1", "키워드2"],
  "simple_explanation": "어려운 개념을 쉽게 재설명"
}
```

**확장 방향**
```
Qwen2.5-7B → (품질 부족 시) Qwen2.5-14B → (속도/품질 필요 시) GPT-5.4-mini API
```

---

## Step 5 — TTS 합성

**담당 모듈:** `src/tts.py`

| 항목 | 내용 |
|------|------|
| 모델 | XTTS v2 (`coqui-tts`) |
| 입력 | LLM 요약문 (str) |
| 출력 | `.wav` 파일 (temp 저장 후 Streamlit 바인딩) |
| 언어 | `ko` (한국어) |

```
요약문 입력
    ▼
XTTS v2 추론 (MPS)
    ▼
/tmp/output.wav 저장
    ▼
st.audio() 바인딩
```

> ⚠️ **API 폴백:** 로컬 추론 속도 미달 시 ElevenLabs Eleven Multilingual v2 전환
> (무료 월 10,000 크레딧, API KEY 필요)

---

## Step 6 — UI 출력

**담당 모듈:** `src/ui.py` + `app.py`

**레이아웃 구성**
```
┌─────────────────────────────────┐
│  📷 이미지 입력 (카메라 / 업로드)  │
├─────────────────────────────────┤
│  📝 OCR 추출 텍스트 (접기 가능)   │
├─────────────────────────────────┤
│  📄 요약문 + 🔊 오디오 플레이어   │
├─────────────────────────────────┤
│  🧠 퀴즈 (정답 확인 버튼 포함)    │
├─────────────────────────────────┤
│  🔑 핵심 키워드                  │
└─────────────────────────────────┘
```

**상태 관리 (`st.session_state`)**

| 키 | 내용 |
|----|------|
| `ocr_text` | OCR 추출 텍스트 |
| `llm_result` | LLM JSON 결과 |
| `audio_path` | TTS 음성 파일 경로 |
| `quiz_answers` | 사용자 퀴즈 답변 |

---

## 프로젝트 구조

```
read-mate/
├── app.py                  # Streamlit 진입점
├── src/
│   ├── input.py            # 입력 수신 및 타입 분기
│   ├── preprocess.py       # 이미지 전처리 (OpenCV)
│   ├── ocr.py              # OCR (PaddleOCR + TrOCR)
│   ├── llm.py              # LLM 분석 (Qwen2.5)
│   ├── tts.py              # TTS 합성 (XTTS v2)
│   └── ui.py               # UI 컴포넌트
├── pyproject.toml
└── .env                    # API 키 관리
```

---

## 에러 처리 전략

| 단계 | 에러 상황 | 처리 |
|------|----------|------|
| OCR | 신뢰도 전체 낮음 | HDX-005 API 폴백 |
| LLM | JSON 파싱 실패 | 재시도 (max 3회) → 원문 텍스트 반환 |
| LLM | 로컬 추론 OOM | Qwen2.5-14B → GPT-5.4-mini 폴백 |
| TTS | 추론 속도 미달 | ElevenLabs API 폴백 |
| 전체 | 예외 발생 | st.error()로 사용자에게 표시 |
