"""
engine/fiscal.py — 재정 시스템

플레이어 세력의 수입·지출·재정 수준 계산과 treasury 자동 갱신을 담당합니다.
context.py (LLM 컨텍스트 표시)와 game.py (턴 틱 갱신) 양쪽에서 공유합니다.
"""

from engine.turn     import parse_ym
from engine.resolver import _get_player_faction_id
from scenarios_loader import GARRISON_POINTS_BY_TIER


# fiscal_level 판정 — balance_ratio = fiscal_balance / income_score 기준
# (ratio_threshold, label, fiscal_mult)
FISCAL_RATIO_THRESHOLDS: list[tuple] = [
    ( 0.10, "풍요", 1.5),
    ( 0.00, "안정", 1.0),
    (-0.05, "균형", 0.7),
    (-0.15, "적자", 0.3),
    ( None, "파산", 0.05),
]

# income_score == 0 (영토·지원금 없음)일 때 fiscal_balance 절댓값으로 판정
FISCAL_ABS_THRESHOLDS: list[tuple] = [
    ( 20,  "풍요", 1.5),
    (  0,  "안정", 1.0),
    (-20,  "균형", 0.7),
    (-60,  "적자", 0.3),
    (None, "파산", 0.05),
]


def fiscal_level(value: float, thresholds: list) -> tuple[str, float]:
    """임계값 테이블에서 재정 수준 레이블과 fiscal_mult를 반환합니다."""
    for thr, label, mult in thresholds:
        if thr is None or value >= thr:
            return label, mult
    return "파산", 0.05


def compute_player_fiscal(state: dict, tpp: int) -> dict | None:
    """플레이어 세력의 재정 상태를 계산합니다.

    Returns:
        dict with keys:
          fid, income_score, expense_score, fiscal_balance,
          fiscal_level, fiscal_mult, treasury,
          ratio_str (표시용), treasury_str (표시용)
        또는 None (플레이어 세력 없음 / tpp 없음)
    """
    if not tpp:
        return None
    player_fid = _get_player_faction_id(state)
    if not player_fid:
        return None
    factions  = state.get("factions",  {})
    locations = state.get("locations", {})
    faction   = factions.get(player_fid, {})
    if not isinstance(faction, dict):
        return None

    # 영토 수입: Σ tier_pts × garrison_modifier (지배 거점)
    territorial = sum(
        GARRISON_POINTS_BY_TIER.get(loc.get("tier", ""), 0)
        * loc.get("garrison_modifier", 1.0)
        for loc in locations.values()
        if isinstance(loc, dict) and loc.get("controller") == player_fid
    )
    income_mult  = float(faction.get("income_mult", 1.0) or 1.0)
    income_flat  = int(faction.get("income_flat", 0)   or 0)
    income_score = round(territorial * income_mult + income_flat)

    # 지출: 야전군
    field_army    = faction.get("field_army", 0) or 0
    expense_score = round(field_army / tpp)

    fiscal_balance = income_score - expense_score
    treasury       = int(faction.get("treasury", 0) or 0)

    # fiscal_level 판정
    if income_score > 0:
        ratio = fiscal_balance / income_score
        f_level, f_mult = fiscal_level(ratio, FISCAL_RATIO_THRESHOLDS)
        ratio_str = f"{ratio:+.1%}"
    else:
        f_level, f_mult = fiscal_level(fiscal_balance, FISCAL_ABS_THRESHOLDS)
        ratio_str = f"{fiscal_balance:+d}pt"

    return {
        "fid":            player_fid,
        "income_score":   income_score,
        "expense_score":  expense_score,
        "fiscal_balance": fiscal_balance,
        "fiscal_level":   f_level,
        "fiscal_mult":    f_mult,
        "treasury":       treasury,
        "ratio_str":      ratio_str,
        "treasury_str":   f"{treasury:+d}pt",
    }


def auto_treasury_update(
    state: dict,
    state_updates: dict,
    fiscal_info: dict | None,
) -> None:
    """경과 시간에 따라 플레이어 세력의 treasury를 자동 갱신합니다.

    LLM이 출력한 treasury_changes(일회성 수입·지출)도 합산합니다.
    결과는 state_updates["treasury_update"] = {"id": fid, "value": new_value}.
    """
    if not fiscal_info:
        return
    prev_ts = state.get("progress", {}).get("timestamp", "")
    new_ts  = state_updates.get("timestamp") or prev_ts
    prev_ym = parse_ym(prev_ts)
    new_ym  = parse_ym(new_ts)
    if not prev_ym or not new_ym:
        return
    elapsed = (new_ym[0] - prev_ym[0]) * 12 + (new_ym[1] - prev_ym[1])
    if elapsed <= 0:
        return

    fid            = fiscal_info["fid"]
    income_score   = fiscal_info["income_score"]
    fiscal_balance = fiscal_info["fiscal_balance"]
    treasury       = fiscal_info["treasury"]

    # 자동 월간 수지 누적
    auto_delta = fiscal_balance * elapsed

    # LLM 일회성 treasury_changes — 플레이어 세력분만 합산
    llm_delta = sum(
        int(r.get("delta", 0))
        for r in (state_updates.get("treasury_changes") or [])
        if isinstance(r, dict) and r.get("id") == fid
    )

    # 상·하한: income_score 기준 ±6개월치 (일회성 지출 버퍼 역할)
    ref   = income_score if income_score > 0 else max(abs(fiscal_info["expense_score"]), 100)
    max_t =  ref * 6
    min_t = -ref * 6

    new_treasury = max(min_t, min(max_t, treasury + round(auto_delta) + llm_delta))
    state_updates["treasury_update"] = {"id": fid, "value": int(new_treasury)}
