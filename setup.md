# 환경 설정
## Visual Studio Code
### 확장 프로그램
#### 필수
![alt text](md_images/python.png)
![alt text](md_images/jupyter.png)
![alt text](md_images/ruff.png)
#### 선택
##### 들여쓰기를 색깍로 구분 가능해 들여쓰기가 맞는지 확인하기 용이
![alt text](md_images/indent-rainbow.png)
##### 아이콘 이쁘게 하고 싶으면 설치
![alt text](md_images/jetbrains-icon.png)

## 파이썬 가상환경 설치
```py
uv venv
.venv/Script/activate
```

## 패키지 설치
```
uv sync
uv pip install -e . # 내부 패키지 사용시 필요
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
