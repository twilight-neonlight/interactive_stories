@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo  Interactive Stories
echo  ==================
echo.

:: Python 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo        https://www.python.org/downloads/ 에서 Python 3.10 이상을 설치하세요.
    echo        설치 시 "Add Python to PATH" 옵션을 반드시 체크하세요.
    pause
    exit /b 1
)

:: API 키 확인
if not exist backend\.env (
    echo [안내] API 키 설정이 필요합니다.
    echo.
    echo  1. https://aistudio.google.com 에서 무료 API 키를 발급받으세요.
    echo  2. 아래에 열리는 메모장에 발급받은 키를 붙여넣고 저장하세요.
    echo     예) GOOGLE_API_KEY=AIzaSy...
    echo.
    echo GOOGLE_API_KEY=여기에_키를_입력하세요 > backend\.env
    notepad backend\.env
    echo.
    echo 저장했으면 아무 키나 누르세요...
    pause >nul
)

:: 가상환경 생성 및 패키지 설치
if not exist .venv (
    echo [1/2] 패키지 설치 중... (최초 1회만 실행됩니다)
    python -m venv .venv
    .venv\Scripts\pip install -r backend\requirements.txt -q --no-warn-script-location
    if errorlevel 1 (
        echo [오류] 패키지 설치에 실패했습니다.
        pause
        exit /b 1
    )
    echo [2/2] 설치 완료.
    echo.
)

:: 브라우저 자동 열기 (서버 준비 전 2초 대기)
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"

:: 서버 실행
echo  서버 주소: http://localhost:8000
echo  종료:      Ctrl+C
echo.
cd backend
"%~dp0.venv\Scripts\uvicorn" main:app --port 8000