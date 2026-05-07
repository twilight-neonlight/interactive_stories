"""
backend/gemini_client.py — Gemini API 호출 헬퍼
"""

import asyncio
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


async def call_gemini_json(messages: list[dict],
                           max_retries: int = 2,
                           retry_delay: float = 2.5) -> str | None:
    """
    소형 JSON 응답 전용 Gemini 호출.
    429 수신 시 retry_delay 초 대기 후 재시도.
    최종 실패 시 None 반환 (예외 미발생).
    """
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    GEMINI_URL,
                    headers={
                        "Authorization": f"Bearer {GOOGLE_API_KEY}",
                        "Content-Type":  "application/json",
                    },
                    json={
                        "model":       MODEL,
                        "messages":    messages,
                        "max_tokens":  256,
                        "temperature": 0.1,
                    },
                )
            if resp.status_code == 429:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    continue
                return None
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception:
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                continue
            return None
    return None
