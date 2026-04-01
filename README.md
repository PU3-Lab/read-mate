[환경 설정](setup.md)

[기획 및 기술 스택](Plan-TechStack.md)

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