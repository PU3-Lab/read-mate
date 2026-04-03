# ReadMate

이미지 문서, PDF, 녹음 파일을 입력받아 텍스트를 추출하고 요약·정리·질의응답을 제공하는 Streamlit 기반 학습 보조 도구.

## 기술 스택

| 역할 | 모델/도구 |
|------|---------|
| OCR | Qwen2.5-VL-7B-Instruct (4-bit NF4 양자화) |
| PDF 추출 | pypdf (텍스트형) + Qwen2.5-VL (스캔형) |
| STT | faster-whisper |
| LLM | Qwen2.5-7B-Instruct / GPT-5.4-mini (폴백) |
| UI | Streamlit |

## 실행 방법

```bash
uv sync
uv run python test_ocr.py   # OCR 단독 테스트
```

## 문서

- [환경 설정](setup.md)
- [기술 스택](Plan-TechStack.md)
- [파이프라인 설계](Plan-Pipeline.md)

## 폴더 규칙
* 공통 파일은 src 폴더에서 작업
* jupyter notebook 파일은 notebooks 폴더에서 작업

[클로드 코드 구조]

your-project/
├── CLAUDE.md                # 🟢 Team instructions (팀 지침)
├── CLAUDE.local.md          # 🟡 Personal overrides (개인 설정 덮어쓰기)
└── .claude/
    ├── settings.json        # 🟢 Permissions + config (권한 및 구성)
    ├── settings.local.json  # 🟡 Personal permissions (개인 권한 설정)
    ├── commands/            # 🟢 Custom slash commands (커스텀 명령어)
    │   ├── review.md        # instructs Claude to do a code review
    │   ├── fix-issue.md     # takes an issue and applies a fix
    │   └── deploy.md        # runs deployment steps
    ├── rules/               # 🟢 Modular instruction files (모듈형 지침)
    │   ├── code-style.md    # enforces formatting, naming, style conventions
    │   ├── testing.md       # defines how tests should be written
    │   └── api-conventions.md # sets rules for API design patterns
    ├── skills/              # 🟣 Auto invoked workflows (자동 호출 워크플로우)
    │   ├── security-review/ # deep security audit workflow
    │   └── deploy/          # structured deployment checklist workflow
    └── agents/              # 🔴 Subagent personals - isolated context (서브 에이전트)
        ├── code-reviewer.md # focused purely on reviewing code
        └── security-auditor.md # specialized in security analysis
## LLM 점검 스크립트
* 실행 스크립트는 `scripts/` 폴더에 둔다
* `Gemma`, `Qwen`, `GPT`를 선택해 샘플 본문 요약과 QA를 점검할 수 있다

```powershell
python scripts/run_llm_check.py
python scripts/run_llm_check.py --engine gemma --sample science_climate --qa
python scripts/run_llm_check.py --engine qwen --sample history_printing
python scripts/run_llm_check.py --engine gpt --sample study_memory --qa
python scripts/run_llm_check.py --list-samples
```
