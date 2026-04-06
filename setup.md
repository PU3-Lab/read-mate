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

## Zonos 추가 요구사항

`Zonos`는 일반 Python 패키지만으로 끝나지 않고 시스템 라이브러리와 공식 소스 설치가 추가로 필요하다.

### 1. eSpeak 설치

macOS
```bash
brew install espeak-ng
```

Ubuntu / Debian
```bash
sudo apt install -y espeak-ng
```

Windows
```text
eSpeak NG를 수동 설치하고 필요하면 PHONEMIZER_ESPEAK_LIBRARY 환경변수를 설정
```

### 2. 공식 Zonos 소스 설치

PyPI wheel 대신 공식 저장소 소스 설치를 권장한다.

```bash
git clone https://github.com/Zyphra/Zonos.git /tmp/Zonos
uv pip install -e /tmp/Zonos
```

### 3. 확인

```bash
uv run python - <<'PY'
from zonos.model import Zonos
print('OK', Zonos)
PY
```
