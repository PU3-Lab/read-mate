# ReadMate OCR 테스트 진행 상황

## ✓ 완료된 작업

### 1. 코드 구현
- **`src/services/ocr_service.py`**: PaddleOCREngine (싱글톤 패턴)
- **`src/services/pdf_service.py`**: PyPDFEngine (텍스트형/스캔형 PDF 분기)
- **`src/pipelines/reading_pipeline.py`**: 전체 파이프라인 오케스트레이터
- **`src/services/base.py`**: ABC 인터페이스 정의
- **`src/models/schemas.py`**: 데이터 계약 정의

### 2. 테스트 검증
- ✓ Mock OCR/PDF/STT/LLM/TTS로 파이프라인 전체 흐름 검증
- ✓ 싱글톤 패턴 작동 확인
- ✓ 입출력 데이터 타입 검증
- ✓ 이미지/PDF/오디오/질문 분기 로직 확인

### 3. Import 경로 수정
- ✓ `src.services.base` — `models.schemas` → `src.models.schemas` 수정
- ✓ `src.pipelines.reading_pipeline` — `models.schemas` → `src.models.schemas` 수정

## ⚠️ 현재 상황: PaddleOCR 런타임 호환성

### 문제
최신 PaddleOCR(2.7.0 이상) + paddlepaddle 3.3.x에서 CUDA 관련 런타임 에러 발생:
```
NotImplementedError: ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]
```

### 원인
- Paddle 3.x로 업그레이드되면서 내부 IR(Intermediate Representation) 변경
- oneDNN과의 호환성 문제 (기하급수적 속성 처리)

### 해결 방법 (추천 순서)

#### 방법 1: PaddleOCR CPU 모드 (즉시 사용)
```bash
# 환경 변수 설정 후 실행
set FLAGS_use_mkldnn=False
uv run python notebooks/hyunwook/test_ocr.py
```
- 장점: 바로 테스트 가능
- 단점: 속도 느림 (~5초/이미지)

#### 방법 2: paddlepaddle CUDA 명시 설치 (권장)
```bash
# pyproject.toml 수정
[tool.uv.sources]
paddlepaddle = [{url = "https://...paddlepaddle-gpu-cu126...", marker = "sys_platform == 'win32'"}]

# 재설치
uv sync --refresh
```
- 장점: GPU 가속 지원, 빠름
- 단점: 설정 필요

#### 방법 3: 구버전 Paddle 사용
```bash
# pyproject.toml
paddlepaddle = "2.5.1"
paddleocr = "2.7.0.3"
opencv-python = "<=4.6.0.66"
```
- 장점: 안정적
- 단점: 최신 기능 미지원

## 📋 테스트 방법

### 현재 즉시 실행 가능
```bash
# 파이프라인 Mock 테스트 (성공함)
uv run python notebooks/hyunwook/test_pipeline_mock.py
```