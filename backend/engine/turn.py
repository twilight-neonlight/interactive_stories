"""
engine/turn.py — 턴 파싱 엔진

LLM 응답 텍스트에서 시각과 STATE_UPDATE 블록을 추출합니다.
"""

import re
import json


_SEASON_TO_MONTH = {
    "초봄": "2월", "봄":   "3월", "늦봄":  "4월",
    "초여름": "5월", "여름": "6월", "늦여름": "7월",
    "초가을": "8월", "가을": "9월", "늦가을": "10월",
    "초겨울": "11월", "겨울": "12월", "늦겨울": "1월",
}

def _normalize_season(ts: str) -> str:
    """계절 표현이 포함된 타임스탬프를 숫자 월로 변환합니다."""
    for season, month in _SEASON_TO_MONTH.items():
        if season in ts:
            return ts.replace(season, month)
    return ts


def extract_timestamp(text: str) -> str:
    """**시각:** 줄을 우선 추출하고, 없으면 본문에서 '연도+장소' 패턴을 탐색합니다."""
    m = re.search(r"\*\*시각:\*\*\s*([^\n]+)", text)
    if m:
        return _normalize_season(m.group(1).strip())
    m = re.search(r"\*시각:\*\s*([^\n]+)", text)
    if m:
        return _normalize_season(m.group(1).strip())
    m = re.search(r"(\d{3,4}년[^。\n]{2,30}[,，、]\s*[가-힣A-Za-z][^\n]{0,20})", text)
    return _normalize_season(m.group(1).strip()) if m else ""


def extract_state_update(text: str) -> tuple[str, dict]:
    """[STATE_UPDATE]{...} 블록을 파싱하고 본문에서 제거해 반환합니다."""
    m = re.search(r'\[STATE_UPDATE\]\s*(\{[\s\S]*?\})\s*(?:```|$)', text)
    if not m:
        m = re.search(r'```state_update\s*([\s\S]*?)\s*```', text)
    if not m:
        return text, {}
    try:
        data = json.loads(m.group(1))
    except Exception:
        data = {}
    cleaned = (text[:m.start()].rstrip() + "\n" + text[m.end():].lstrip()).strip()
    return cleaned, data


def turn_engine(content: str, state: dict) -> dict:
    """
    LLM 응답과 현재 state를 받아 다음 state_updates를 반환합니다.
    장/씬 구분은 더 이상 LLM 출력 형식이나 상태 업데이트로 사용하지 않습니다.
    """
    return {"timestamp": extract_timestamp(content)}
