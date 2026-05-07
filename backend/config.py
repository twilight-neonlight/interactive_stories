"""
backend/config.py — 환경변수·모델 설정 중앙화
"""

import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다. .env 파일을 확인하세요.")

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    import secrets
    SECRET_KEY = secrets.token_hex(32)
    import warnings
    warnings.warn(
        "SECRET_KEY가 설정되지 않아 임시 키를 사용합니다. "
        "서버 재시작 시 모든 토큰이 무효화됩니다. "
        "backend/.env에 SECRET_KEY=<랜덤 문자열>을 추가하세요.",
        stacklevel=1,
    )

_root = Path(__file__).parent.parent
SYSTEM_PROMPT = "\n\n".join(
    (_root / name).read_text(encoding="utf-8")
    for name in ("prompt_rules.md", "prompt_output_format.md", "prompt_examples.md")
)

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")

MODEL       = "gemini-3-flash-preview"
MAX_TOKENS  = 9172
TEMPERATURE = 0.8
GEMINI_URL = "https://factchat-cloud.mindlogic.ai/v1/gateway/chat/completions"
# GEMINI_URL  = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
