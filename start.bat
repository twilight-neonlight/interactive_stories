@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo  Interactive Stories
echo  ==================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed.
    echo         Download Python 3.10+ from https://www.python.org/downloads/
    echo         Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: Check API key
if not exist backend\.env (
    echo [SETUP] API key required.
    echo.
    echo  1. Get a free API key at https://aistudio.google.com
    echo  2. Paste your key into the Notepad window that will open.
    echo     Example: GOOGLE_API_KEY=AIzaSy...
    echo.
    echo GOOGLE_API_KEY=your_key_here > backend\.env
    notepad backend\.env
    echo.
    echo Press any key after saving...
    pause >nul
)

:: Create venv and install packages
if not exist .venv (
    echo [1/2] Installing packages... (first run only)
    python -m venv .venv
    .venv\Scripts\pip install -r backend\requirements.txt -q --no-warn-script-location
    if errorlevel 1 (
        echo [ERROR] Package installation failed.
        pause
        exit /b 1
    )
    echo [2/2] Done.
    echo.
)

:: Open browser after 2s delay
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"

:: Start server
echo  Server: http://localhost:8000
echo  Stop:   Ctrl+C
echo.
cd backend
"%~dp0.venv\Scripts\uvicorn" main:app --port 8000