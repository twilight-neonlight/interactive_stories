"""
engine/conquest.py — 거점 점령 및 주둔군 갱신

점령 감지, garrison_modifier 재계산, 처분 분류 로직을 담당합니다.
"""

from engine.turn import parse_ym, ts_ym_only
from scenarios_loader import (
    GARRISON_POINTS_BY_TIER,
    CONQUEST_DISPOSITIONS,
    GARRISON_RECOVERY_PER_MONTH,
)


def classify_conquest_disposition(command: str) -> str | None:
    """명령어에서 점령지 처분 유형을 추출합니다."""
    if "초토화" in command:
        return "초토화"
    if "약탈" in command:
        return "약탈"
    if "피해" in command or "최소화" in command or "보호" in command:
        return "피해 최소화"
    return None


def apply_garrison_updates(
    state: dict,
    new_ts: str,
    tpp: int,
    loc_change_map: dict,
    admin_mult: float = 1.0,
    fiscal_mult: float = 1.0,
) -> list[dict]:
    """garrison 관련 location_changes를 loc_change_map에 in-place로 병합합니다.

    처리 순서:
    1. 이번 턴 controller 변경 거점 → garrison_modifier=0.3(임시), conquered_at=new_ts 기록
    2. conquered_at이 있는 처분 확정 거점 → 경과 시간 기반 모디파이어 재계산

    반환: 새로 점령된 거점 목록 (처분 대기)
    """
    old_locations = state.get("locations", {})
    newly_pending: list[dict] = []

    # 1. 이번 턴 점령 감지 — 양측 모두 명확한 지배 세력인 경우만 처분 대상
    for lid, lc in loc_change_map.items():
        new_ctrl = lc.get("controller")
        old_ctrl = old_locations.get(lid, {}).get("controller")
        if (new_ctrl and old_ctrl
                and new_ctrl != old_ctrl
                and old_ctrl != "contested"
                and new_ctrl != "contested"):
            lc["garrison_modifier"] = 0.3  # 처분 확정 전 임시값
            lc["conquered_at"]      = ts_ym_only(new_ts)
            tier     = old_locations.get(lid, {}).get("tier", "")
            base_pts = GARRISON_POINTS_BY_TIER.get(tier, 0)
            lc["garrison"] = round(base_pts * 0.3 * tpp)
            newly_pending.append({
                "id":           lid,
                "tier":         tier,
                "name":         old_locations.get(lid, {}).get("name", lid),
                "conquered_at": lc["conquered_at"],
            })

    # 2. 처분 확정 점령 거점 시간 경과 회복
    # garrison_modifier(t) = base + elapsed_months × GARRISON_RECOVERY_PER_MONTH
    new_ym = parse_ym(new_ts)
    for lid, loc in old_locations.items():
        if lid in loc_change_map:
            continue
        conquered_at         = loc.get("conquered_at")
        conquest_disposition = loc.get("conquest_disposition")
        if not conquered_at or not conquest_disposition:
            continue
        cym = parse_ym(conquered_at)
        if not cym or not new_ym:
            continue
        elapsed  = (new_ym[0] - cym[0]) * 12 + (new_ym[1] - cym[1])
        base     = CONQUEST_DISPOSITIONS.get(conquest_disposition, {}).get("base", 0.3)
        new_mod  = min(1.0, base + max(0, elapsed) * GARRISON_RECOVERY_PER_MONTH * admin_mult * fiscal_mult)
        tier     = loc.get("tier", "")
        base_pts = GARRISON_POINTS_BY_TIER.get(tier, 0)
        change: dict = {
            "id":                lid,
            "garrison_modifier": round(new_mod, 4),
            "garrison":          round(base_pts * new_mod * tpp),
        }
        if new_mod >= 1.0:
            change["conquered_at"]         = None
            change["conquest_disposition"] = None
            change["garrison_modifier"]    = 1.0
        loc_change_map[lid] = change

    return newly_pending
