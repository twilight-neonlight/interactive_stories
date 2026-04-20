"""
backend/gemini_client.py — Gemini API 호출 헬퍼
"""

import httpx
from fastapi import HTTPException
from config import GOOGLE_API_KEY, MODEL, MAX_TOKENS, TEMPERATURE, GEMINI_URL


async def call_gemini(messages: list[dict]) -> str:
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                GEMINI_URL,
                headers={
                    "Authorization": f"Bearer {GOOGLE_API_KEY}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model":       MODEL,
                    "messages":    messages,
                    "max_tokens":  MAX_TOKENS,
                    "temperature": TEMPERATURE,
                },
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Gemini API 오류: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gemini API 오류: {e}")
    return resp.json()["choices"][0]["message"]["content"]
