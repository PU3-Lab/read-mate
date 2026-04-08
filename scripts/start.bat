@echo off
REM ReadMate 서버 + Streamlit 동시 실행 스크립트 (Windows)
REM
REM 사용법:
REM   scripts\start.bat
REM   scripts\start.bat --server-port 8080 --app-port 8502
REM   set LLM_ENGINE=openai && scripts\start.bat

setlocal

set SERVER_PORT=8000
set APP_PORT=8501

:parse_args
if "%~1"=="--server-port" (
    set SERVER_PORT=%~2
    shift & shift & goto parse_args
)
if "%~1"=="--app-port" (
    set APP_PORT=%~2
    shift & shift & goto parse_args
)

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..

cd /d "%PROJECT_ROOT%"

echo ==========================================
echo   ReadMate 전체 시작
echo   LLM 서버 : http://localhost:%SERVER_PORT%
echo   앱       : http://localhost:%APP_PORT%
if defined LLM_ENGINE (
    echo   엔진     : %LLM_ENGINE%
) else (
    echo   엔진     : openai (기본)
)
echo ==========================================
echo.

REM LLM 서버 — 새 터미널 창
start "ReadMate · LLM Server :%SERVER_PORT%" cmd /k ^
  "title ReadMate · LLM Server :%SERVER_PORT% && cd /d %PROJECT_ROOT% && uv run uvicorn backend.main:app --host 0.0.0.0 --port %SERVER_PORT% --reload"

REM 서버 기동 대기
timeout /t 2 /nobreak > nul

REM Streamlit — 새 터미널 창
start "ReadMate · Streamlit :%APP_PORT%" cmd /k ^
  "title ReadMate · Streamlit :%APP_PORT% && cd /d %PROJECT_ROOT% && set LLM_SERVER_URL=http://localhost:%SERVER_PORT% && uv run streamlit run frontend/app.py --server.port %APP_PORT%"

echo 두 터미널 창이 열렸습니다.
echo   LLM 서버 : http://localhost:%SERVER_PORT%
echo   앱       : http://localhost:%APP_PORT%

endlocal
