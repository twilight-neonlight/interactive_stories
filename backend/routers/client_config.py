"""
routers/config.py — 클라이언트가 필요로 하는 게임 메타데이터 API

프론트엔드에서 하드코딩하면 백엔드와 이중 관리가 필요한 상수들을
단일 엔드포인트로 제공한다.

  GET /api/config
  → {
      grade_scale:   string[],       // F…S (17단계)
      weather_meta:  { [key]: { label, atk, def } },
      terrain_meta:  { [key]: { label, def_bonus, atk_penalty } },
    }
"""

from fastapi import APIRouter
from engine.resolver import (
    _GRADE_SCALE,
    _WEATHER_TABLE,
    _TERRAIN_TABLE,
)

router = APIRouter()


@router.get("/api/config")
def get_config():
    weather_meta = {
        key: {
            "label":  label,
            "atk":    atk,   # 공격측 수정치 (음수 = 불리)
            "def":    def_,  # 방어측 수정치 (양수 = 유리)
            # UI 표시용 effect 문자열 — 백엔드 수치에서 자동 생성
            "effect": _fmt_effect(atk, def_),
        }
        for key, (atk, def_, label) in _WEATHER_TABLE.items()
        if label  # clear(label="")는 제외해도 되지만 키는 포함
    } | {
        "clear": {"label": "맑음", "atk": 0, "def": 0, "effect": "효과 없음"},
    }

    terrain_meta = {
        key: {
            "label":       label,
            "def_bonus":   def_bonus,    # 방어측 보너스
            "atk_penalty": atk_penalty,  # 공격측 패널티 (저장은 음수 그대로)
            "effect":      _fmt_effect(atk_penalty, def_bonus),
        }
        for key, (def_bonus, atk_penalty, label) in _TERRAIN_TABLE.items()
    }

    return {
        "grade_scale":  list(_GRADE_SCALE),
        "weather_meta": weather_meta,
        "terrain_meta": terrain_meta,
    }


def _fmt_effect(atk: int, def_: int) -> str:
    """수치 → 'A 공격 −1 / 수비 +2' 형태 문자열. 0인 항목은 생략."""
    parts = []
    if atk != 0:
        parts.append(f"공격 {'+' if atk > 0 else ''}{atk}")
    if def_ != 0:
        parts.append(f"수비 {'+' if def_ > 0 else ''}{def_}")
    return " / ".join(parts) if parts else "효과 없음"
