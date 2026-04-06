@echo off
REM ReadMate Streamlit 앱 실행 스크립트 (Windows)
REM
REM 사용법:
REM   scripts\start_app.bat
REM   scripts\start_app.bat --port 8502
REM   set LLM_SERVER_URL=http://localhost:9000 && scripts\start_app.bat

setlocal

set PORT=8501

:parse_args
if "%~1"=="--port" (
    set PORT=%~2
    shift
    shift
    goto parse_args
)

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..

cd /d "%PROJECT_ROOT%"

echo ReadMate Streamlit 앱 시작
echo   포트          : %PORT%
echo   앱 주소       : http://localhost:%PORT%
if defined LLM_SERVER_URL (
    echo   LLM 서버 주소 : %LLM_SERVER_URL%
) else (
    echo   LLM 서버 주소 : http://localhost:8000
)
echo.

uv run streamlit run frontend/app.py --server.port %PORT%

endlocal
