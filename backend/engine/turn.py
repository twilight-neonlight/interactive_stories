"""
engine/turn.py — 턴 파싱 엔진

LLM 응답 텍스트에서 구조적 신호(장/씬 번호, 시각, STATE_UPDATE 블록)를 추출합니다.
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


def _extract_chapter_title(text: str) -> str:
    """SCENE 1 직전에 오는 짧은 헤딩을 장 제목으로 추출합니다."""
    m = re.search(r"^#{0,3}\s*(.{2,30})\s*$(?=[\s\S]*SCENE\s*1\b)", text, re.MULTILINE)
    if m and "장" not in m.group(1):
        return m.group(1).strip()
    return ""


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
    우선순위: 장 종결 > 새 장 시작 > 씬 진행 > fallback(씬 +1)
    """
    progress    = state.get("progress", {})
    cur_chapter = progress.get("chapter", 1)
    cur_scene   = progress.get("scene",   1)
    cur_title   = progress.get("chapterTitle", "")

    if re.search(r"장\s*종결|Chapter\s*\d+\s*Concluded|Chapter\s*Close", content, re.IGNORECASE):
        return {
            "scene":          cur_scene,
            "chapter":        cur_chapter,
            "chapter_title":  cur_title,
            "timestamp":      extract_timestamp(content),
            "is_chapter_end": True,
        }

    m = re.search(r"##\s*(\d+)장,?\s*SCENE\s*1\b", content, re.IGNORECASE)
    if m:
        return {
            "scene":          1,
            "chapter":        int(m.group(1)),
            "chapter_title":  _extract_chapter_title(content),
            "timestamp":      extract_timestamp(content),
            "is_chapter_end": False,
        }

    m = re.search(r"##\s*\d+장,?\s*SCENE\s*(\d+)", content, re.IGNORECASE)
    if m:
        return {
            "scene":          int(m.group(1)),
            "chapter":        cur_chapter,
            "chapter_title":  cur_title,
            "timestamp":      extract_timestamp(content),
            "is_chapter_end": False,
        }

    return {
        "scene":          cur_scene + 1,
        "chapter":        cur_chapter,
        "chapter_title":  cur_title,
        "timestamp":      extract_timestamp(content),
        "is_chapter_end": False,
    }
