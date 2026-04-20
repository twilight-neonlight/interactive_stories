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

_root = Path(__file__).parent.parent
SYSTEM_PROMPT = "\n\n".join(
    (_root / name).read_text(encoding="utf-8")
    for name in ("prompt_rules.md", "prompt_output_format.md", "prompt_examples.md")
)

MODEL       = "gemini-3-flash-preview"
MAX_TOKENS  = 9172
TEMPERATURE = 0.8
GEMINI_URL  = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
