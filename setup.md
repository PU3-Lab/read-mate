# 환경 설정

## 1. 가상환경 / 패키지

```bash
uv sync
```

내부 패키지 import 문제를 피하려면 editable 설치도 같이 권장:

```bash
uv pip install -e .
```

## 2. 환경 변수

루트에 `.env`를 두고 필요한 키를 설정한다.

```env
LLM_ENGINE=gemma
LLM_SERVER_URL=http://localhost:8000
OPENAI_API_KEY=
ELEVENLABS_API_KEY=
```

## 3. LLM 서버 실행

macOS / Linux:

```bash
./scripts/start_server.sh
```

Windows:

```powershell
scripts\start_server.bat
```

포트 변경 예시:

```bash
./scripts/start_server.sh --port 8001
```

## 4. Streamlit 앱 실행

macOS / Linux:

```bash
./scripts/start_app.sh
```

Windows:

```powershell
scripts\start_app.bat
```

포트 변경 예시:

```bash
./scripts/start_app.sh --port 8502
```

서버 주소를 바꾸는 예시:

```bash
LLM_SERVER_URL=http://localhost:8001 ./scripts/start_app.sh
```

## 5. 직접 실행 명령

스크립트를 쓰지 않을 때:

```bash
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
uv run streamlit run scripts/app.py --server.port 8501
```

## 6. 확인용 테스트

```bash
uv run pytest tests/test_app.py tests/test_llm_remote.py tests/test_reading_pipeline.py
```
