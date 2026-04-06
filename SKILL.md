# ReadMate Pipeline — SKILL.md

## 목적
종이책 페이지 이미지 → OCR → LLM 분석 → TTS 낭독
Streamlit 기반 로컬 학습 보조 도구

## 환경 (공통)
- Python: uv 가상환경
- OCR: PaddleOCR (한/영 1차) + Surya (레이아웃 복잡 페이지 보조)
- LLM: Ollama — exaone3.5:7.8b (한국어 특화, LG AI)
- TTS: Edge-TTS (MVP) → Kokoro / XTTS v2 (고도화 시)
- UI: Streamlit

---

## 🖥️ OS별 환경 세팅

### macOS (Apple Silicon — 주 개발 환경)

**제약**
- MPS 백엔드 사용
- fp16 NaN 이슈 → bf16 강제 적용
- CUDA 전용 패키지 사용 불가
- PaddlePaddle: CPU 빌드 사용 (MPS 미지원)

**사전 준비**
```bash
brew install uv ollama opencv
ollama serve
```

**가상환경 & 패키지**
```bash
uv venv --python 3.11 && source .venv/bin/activate
uv pip install -e .
```

**주의사항**
- `paddlepaddle` CPU 빌드만 사용 (GPU 버전 X)
- xformers 사용 불가
- torch 필요 시 MPS 자동 감지됨

---

### Windows

**제약**
- CUDA GPU 있으면 CUDA 백엔드 사용 가능
- 경로 구분자 `\` 주의 → 코드에서 `pathlib.Path` 사용 권장

**사전 준비**
```powershell
winget install astral-sh.uv
# Ollama: https://ollama.com/download/windows 에서 인스톨러 실행
```

**가상환경 & 패키지**
```powershell
uv venv --python 3.11
.venv\Scripts\activate
uv pip install -e .

# CUDA GPU 환경 (선택)
uv pip install paddlepaddle-gpu
uv pip install torch --index-url https://download.pytorch.org/whl/cu121
```

**주의사항**
- Streamlit 실행: `python -m streamlit run scripts/app.py` 권장
- Ollama 시스템 트레이에서 자동 실행
- OpenCV는 pip으로 자동 설치 (별도 설치 불필요)

---

### Linux (Ubuntu 22.04+ / Debian)

**사전 준비**
```bash
sudo apt install -y python3.11-dev libopencv-dev libgl1 libglib2.0-0
curl -LsSf https://astral.sh/uv/install.sh | sh
curl -fsSL https://ollama.com/install.sh | sh && ollama serve &
```

**가상환경 & 패키지**
```bash
uv venv --python 3.11 && source .venv/bin/activate
uv pip install -e .

# CUDA GPU 환경 (선택)
uv pip install paddlepaddle-gpu
uv pip install torch --index-url https://download.pytorch.org/whl/cu121
```

**주의사항**
- headless 서버: `opencv-python-headless` 사용
- 외부 접근 시: `streamlit run scripts/app.py --server.address 0.0.0.0`
- Ollama systemd 서비스 등록 가능

---

## OS별 차이 요약

| 항목 | macOS (Apple Silicon) | Windows | Linux |
|------|----------------------|---------|-------|
| 백엔드 | MPS | CUDA / CPU | CUDA / CPU |
| fp16 | ❌ bf16 강제 | ✅ CUDA 시 | ✅ CUDA 시 |
| PaddlePaddle | CPU 빌드 | CPU / GPU | CPU / GPU |
| Ollama | brew | 공식 인스톨러 | curl 스크립트 |
| uv | brew | winget | curl |
| OpenCV | brew + pip | pip | apt + pip |

## 모델 선택 근거
| 컴포넌트 | 선택 모델 | 이유 |
|---|---|---|
| OCR 1차 | PaddleOCR | 한/영 문서형 처리 강함 |
| OCR 보조 | Surya | 현대적 레이아웃 인식 |
| LLM | exaone3.5:7.8b | 한국어 책 처리 특화 |
| TTS (MVP) | Edge-TTS | 설치 없이 바로 사용, 고품질 |
| TTS (고도화) | Kokoro / XTTS v2 | 완전 오프라인 원할 때 |

## 프로젝트 구조
```
ReadMate/
├── SKILL.md
├── instructions.md
├── src/
│   ├── app.py        ← Streamlit 엔트리포인트
│   ├── ocr.py        ← PaddleOCR + Surya 모듈
│   ├── llm.py        ← Ollama API 모듈
│   ├── tts.py        ← Edge-TTS 모듈
│   └── utils.py      ← 이미지 전처리 (OpenCV)
├── prompts/
│   ├── summarize.txt
│   ├── quiz.txt
│   └── explain.txt
├── input/
├── output/
│   ├── text/
│   ├── analysis/
│   └── audio/
└── config/
    └── settings.yaml
```

## 파이프라인 단계
1. `input/` 에 이미지 투입 (카메라 or 파일 업로드)
2. `ocr.py` → PaddleOCR 추출 → output/text/ 저장
   - 레이아웃 복잡 시 Surya 보조 투입
3. `llm.py` → Ollama exaone3.5:7.8b 호출
   - prompts/ 템플릿 사용
   - 요약 (3~5문장)
   - 퀴즈 (객관식/OX 2~3개, JSON 형식)
   - 쉬운 설명 / 메모 키워드
4. `tts.py` → Edge-TTS 한국어 음성 합성 → output/audio/ 저장
5. `app.py` → Streamlit UI 전체 결과 표시

## 실행
```bash
# 가상환경 생성 (uv)
uv venv && source .venv/bin/activate

# Ollama 모델 pull
ollama pull exaone3.5:7.8b

# 앱 실행
uv run streamlit run scripts/app.py
```

## 업그레이드 경로
- LLM: exaone3.5:7.8b → qwen2.5:14b (맥락 유지 더 필요 시)
- TTS: Edge-TTS → Kokoro (완전 오프라인 필요 시)
- OCR: PaddleOCR 단독 → PaddleOCR + Surya 혼합 (복잡 레이아웃)
