#!/bin/bash
set -e
cd "$(dirname "$0")"

echo ""
echo " Interactive Stories"
echo " ==================="
echo ""

# Python 확인
if ! command -v python3 &>/dev/null; then
    echo "[오류] Python3가 설치되어 있지 않습니다."
    echo "       https://www.python.org/downloads/ 에서 설치하세요."
    exit 1
fi

# API 키 확인
if [ ! -f backend/.env ]; then
    echo "[안내] API 키 설정이 필요합니다."
    echo ""
    echo " 1. https://aistudio.google.com 에서 무료 API 키를 발급받으세요."
    echo " 2. 아래 명령어를 실행해 키를 입력하세요:"
    echo "    echo 'GOOGLE_API_KEY=발급받은키' > backend/.env"
    echo ""
    echo "GOOGLE_API_KEY=여기에_키를_입력하세요" > backend/.env
    exit 1
fi

# 가상환경 생성 및 패키지 설치
if [ ! -d .venv ]; then
    echo "[1/2] 패키지 설치 중... (최초 1회만 실행됩니다)"
    python3 -m venv .venv
    .venv/bin/pip install -r backend/requirements.txt -q
    echo "[2/2] 설치 완료."
    echo ""
fi

# 브라우저 자동 열기 (서버 준비 전 2초 대기)
(sleep 2 && (open "http://localhost:8000" 2>/dev/null || xdg-open "http://localhost:8000" 2>/dev/null || true)) &

# 서버 실행
echo " 서버 주소: http://localhost:8000"
echo " 종료:      Ctrl+C"
echo ""
cd backend
../.venv/bin/uvicorn main:app --port 8000