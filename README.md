[환경 설정](setup.md)

[기획 및 기술 스택](Plan-TechStack.md)

## 폴더 규칙
* 공통 파일은 src 폴더에서 작업
* jupyter notebook 파일은 notebooks 폴더에서 작업

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
