@echo off
REM ReadMate LLM 서버 실행 스크립트 (Windows)
REM
REM 사용법:
REM   scripts\start_server.bat
REM   scripts\start_server.bat --dev
REM   scripts\start_server.bat --port 8080
REM   scripts\start_server.bat --dev --port 8080
REM   set LLM_ENGINE=openai && scripts\start_server.bat

setlocal

set PORT=28765
set DEV_FLAG=

REM 인자 파싱
:parse_args
if "%~1"=="--port" (
    set PORT=%~2
    shift
    shift
    goto parse_args
)
if "%~1"=="--dev" (
    set DEV_FLAG=--dev
    shift
    goto parse_args
)

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..

cd /d "%PROJECT_ROOT%"

echo ReadMate LLM 서버 시작
echo   포트    : %PORT%
if defined LLM_ENGINE (
    echo   엔진    : %LLM_ENGINE%
) else (
    echo   엔진    : openai (기본)
)
if defined DEV_FLAG (
    echo   모드    : dev (Edge TTS)
) else (
    echo   모드    : prod (ElevenLabs)
)
echo   주소    : http://localhost:%PORT%
echo.

uv run python -m backend.main %DEV_FLAG% --port %PORT%

endlocal
