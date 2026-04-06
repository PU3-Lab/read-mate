# ReadMate

이미지 문서, PDF, 오디오 파일을 입력받아 텍스트를 추출하고 요약·질의응답·음성 읽기를 제공하는 Streamlit 기반 학습 보조 도구.

## 현재 실행 구조

- 앱 UI: `scripts/app.py`
- 앱 오케스트레이터: `src/pipelines/reading_pipeline.py`
- LLM 서버: `backend/main.py`
- LLM 연결 방식: 앱 -> HTTP API (`LLM_SERVER_URL`) -> LLM 서버

## 기술 스택

| 역할 | 모델/도구 |
|------|---------|
| OCR | Qwen2.5-VL-7B-Instruct |
| PDF 추출 | pypdf + Qwen2.5-VL OCR |
| STT | faster-whisper |
| LLM 서버 | Gemma / Qwen / OpenAI |
| 앱 UI | Streamlit |
| TTS | Zonos |

## 빠른 실행

### 1. 의존성 설치

```bash
uv sync
```

### 2. LLM 서버 실행

```bash
./scripts/start_server.sh
```

Windows:

```powershell
scripts\start_server.bat
```

기본 주소는 `http://localhost:8000` 입니다.

### 3. Streamlit 앱 실행

```bash
./scripts/start_app.sh
```

Windows:

```powershell
scripts\start_app.bat
```

기본 주소는 `http://localhost:8501` 입니다.

## 환경 변수

- `LLM_ENGINE`: 서버에서 사용할 LLM 선택 (`gemma`, `qwen`, `openai`)
- `LLM_SERVER_URL`: 앱이 호출할 LLM 서버 주소
- `OPENAI_API_KEY`: `LLM_ENGINE=openai`일 때 필요
- `ELEVENLABS_API_KEY`: ElevenLabs 사용 시 필요

예시:

```bash
LLM_ENGINE=openai ./scripts/start_server.sh
LLM_SERVER_URL=http://localhost:8000 ./scripts/start_app.sh
```

## 테스트

```bash
uv run pytest tests/test_app.py tests/test_llm_remote.py tests/test_reading_pipeline.py
```

## 문서

- [환경 설정](setup.md)
- [기술 스택](Plan-TechStack.md)
- [파이프라인 설계](Plan-Pipeline.md)
- [클로드 폴더 구조](Claude-Folder-Structure.md)

## 현재 상태

- [x] OCR / PDF / STT 서비스 구현
- [x] LLM 서버 분리
- [x] Streamlit 앱에서 파이프라인 연결
- [ ] 로컬 리소스 최적화
