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
if exist ".venv\Scripts\python.exe" goto venv_ready

echo [1/2] Installing packages... (first run only)
python -m venv .venv
if errorlevel 1 (
    echo [ERROR] Virtual environment setup failed.
    pause
    exit /b 1
)
.venv\Scripts\pip install -r backend\requirements.txt -q --no-warn-script-location
if errorlevel 1 (
    echo [ERROR] Package installation failed.
    pause
    exit /b 1
)
echo [2/2] Done.
echo.

:venv_ready

:: Check for latest version on GitHub
git rev-parse --is-inside-work-tree >nul 2>&1
if not errorlevel 1 (
    echo [UPDATE] Checking for latest version...
    git fetch origin >nul 2>&1
    if not errorlevel 1 (
        for /f %%i in ('git rev-parse HEAD') do set _LOCAL=%%i
        for /f %%i in ('git rev-parse @{u} 2^>nul') do set _REMOTE=%%i
        if defined _REMOTE (
            if "!_LOCAL!"=="!_REMOTE!" (
                echo [UPDATE] Already up to date.
            ) else (
                echo [UPDATE] New version available.
                echo.
                set /p _ANSWER= Update now? (Y/N):
                if /i "!_ANSWER!"=="Y" (
                    git pull
                    echo [UPDATE] Reinstalling packages...
                    .venv\Scripts\pip install -r backend\requirements.txt -q --no-warn-script-location
                    echo.
                    echo  Update complete. Please run start.bat again.
                    timeout /t 5 /nobreak >nul
                    exit 0
                ) else (
                    echo [UPDATE] Skipped. Running current local version.
                )
            )
        )
    ) else (
        echo [UPDATE] Could not reach GitHub, skipping version check.
    )
    echo.
)

:: Open browser after 2s delay
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000/frontend/main_menu.html"

:: Start server
echo  Server: http://localhost:8000
echo  Stop:   Ctrl+C
echo.
cd backend
"%~dp0.venv\Scripts\uvicorn" main:app --port 8000
if errorlevel 1 (
    echo.
    echo [ERROR] Server failed to start.
    pause
    exit /b 1
)
