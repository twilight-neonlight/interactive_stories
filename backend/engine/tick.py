"""
engine/tick.py — 턴 자동 갱신 (시간 경과 효과)

매 턴 타임스탬프 경과량에 따라 자동으로 적용되는 상태 변화:
  - battle_damage 회복
  - reserve_manpower 회복
  - 첩보 수준(intel_level) 감쇠
  - strength_score 전체 재계산
"""

from engine.turn     import parse_ym
from engine.resolver import _get_player_faction_id, calc_admin_recovery_multiplier
from scenarios_loader import (
    get_scenario_tpp,
    compute_max_reserve,
    compute_faction_strength,
)


# battle_damage 자동 회복량 (전투 중이 아닌 세력, 게임 내 1개월 경과당)
BATTLE_DAMAGE_RECOVERY_PER_MONTH = 25

# 예비 인력 월간 회복률 (부족분의 X% / 월)
RESERVE_RECOVERY_RATE = 0.08


def auto_battle_damage_recovery(state: dict, state_updates: dict) -> None:
    """타임스탬프 경과에 따른 battle_damage 자동 회복.

    전투 중인 세력(플레이어·적군)은 제외한다.
    거점 점령 처분으로 이미 추가된 faction_battle_recovery와 합산한다.
    """
    prev_ts = state.get("progress", {}).get("timestamp", "")
    new_ts  = state_updates.get("timestamp") or prev_ts

    prev_ym = parse_ym(prev_ts)
    new_ym  = parse_ym(new_ts)
    if not prev_ym or not new_ym:
        return

    elapsed = (new_ym[0] - prev_ym[0]) * 12 + (new_ym[1] - prev_ym[1])
    if elapsed <= 0:
        return

    auto_amount = BATTLE_DAMAGE_RECOVERY_PER_MONTH * elapsed

    excluded: set[str] = set()
    combat_state = state.get("combatState")
    if combat_state and combat_state.get("active"):
        player_fid = _get_player_faction_id(state)
        if player_fid:
            excluded.add(player_fid)
        enemy_fid = combat_state.get("enemy_faction_id")
        if enemy_fid:
            excluded.add(enemy_fid)

    factions = state.get("factions", {})
    existing: dict[str, int] = {
        r["id"]: r["amount"]
        for r in (state_updates.get("faction_battle_recovery") or [])
        if isinstance(r, dict) and r.get("id")
    }

    for fid, faction in factions.items():
        if not isinstance(faction, dict) or fid in excluded:
            continue
        bd = faction.get("battle_damage") or 0
        if bd <= 0:
            continue
        existing[fid] = existing.get(fid, 0) + min(bd, auto_amount)

    if existing:
        state_updates["faction_battle_recovery"] = [
            {"id": fid, "amount": round(amt)} for fid, amt in existing.items()
        ]


def auto_reserve_recovery(
    state: dict, state_updates: dict
) -> None:
    """타임스탬프 경과에 따른 reserve_manpower 자동 회복.

    매월 부족분의 RESERVE_RECOVERY_RATE만큼 회복 (복리 방식).
    LLM이 이미 출력한 faction_reserve_changes와 합산해 반환.
    """
    prev_ts = state.get("progress", {}).get("timestamp", "")
    new_ts  = state_updates.get("timestamp") or prev_ts

    prev_ym = parse_ym(prev_ts)
    new_ym  = parse_ym(new_ts)
    if not prev_ym or not new_ym:
        return

    elapsed = (new_ym[0] - prev_ym[0]) * 12 + (new_ym[1] - prev_ym[1])
    if elapsed <= 0:
        return

    tpp = get_scenario_tpp(state)
    if not tpp:
        return

    factions  = state.get("factions", {})
    locations = state.get("locations", {})

    existing: dict[str, int] = {
        r["id"]: r["delta"]
        for r in (state_updates.get("faction_reserve_changes") or [])
        if isinstance(r, dict) and r.get("id")
    }

    admin_mult = calc_admin_recovery_multiplier(state)
    eff_rate   = min(1.0, RESERVE_RECOVERY_RATE * admin_mult)

    for fid, faction in factions.items():
        if not isinstance(faction, dict) or faction.get("defeated"):
            continue
        reserve     = faction.get("reserve_manpower") or 0
        max_reserve = compute_max_reserve(faction, fid, locations, tpp)
        if max_reserve <= 0 or reserve >= max_reserve:
            continue
        deficit  = max_reserve - reserve
        recovery = round(deficit - deficit * (1 - eff_rate) ** elapsed)
        if recovery > 0:
            existing[fid] = existing.get(fid, 0) + recovery

    if existing:
        state_updates["faction_reserve_changes"] = [
            {"id": fid, "delta": round(amt)} for fid, amt in existing.items()
        ]


_INJURY_RECOVERY_MONTHS: dict[str, int] = {"경상": 2, "중상": 3, "극도": 4}
_INJURY_DOWNGRADE: dict[str, str | None] = {"극도": "중상", "중상": "경상", "경상": None}


def auto_injury_recovery(state: dict, state_updates: dict) -> None:
    """부상 자동 감쇠: 경상 2개월, 중상→경상 3개월, 극도→중상 4개월."""
    new_ts = state_updates.get("timestamp") or state.get("progress", {}).get("timestamp", "")
    new_ym = parse_ym(new_ts)
    if not new_ym:
        return

    chars = state.get("characters", {})
    existing: dict[str, dict] = {
        ic["id"]: ic
        for ic in (state_updates.get("character_injury_changes") or [])
        if isinstance(ic, dict) and ic.get("id")
    }

    for cid, char in chars.items():
        if not isinstance(char, dict):
            continue
        injury = char.get("injury")
        if not injury or cid in existing:
            continue
        since_ym = parse_ym(char.get("injury_since", ""))
        if not since_ym:
            continue
        elapsed = (new_ym[0] - since_ym[0]) * 12 + (new_ym[1] - since_ym[1])
        if elapsed >= _INJURY_RECOVERY_MONTHS.get(injury, 999):
            existing[cid] = {"id": cid, "injury": _INJURY_DOWNGRADE.get(injury)}

    if existing:
        state_updates["character_injury_changes"] = list(existing.values())


def auto_intel_decay(state: dict, state_updates: dict) -> None:
    """타임스탬프 경과에 따른 세력 첩보 수준 자동 감쇠.

    intel_level > 0인 세력의 첩보 수준을 6개월마다 1씩 감쇠.
    감쇠 기준 시각은 state['flags']['intel_decay_{fid}_last']에
    절대 개월 수(year × 12 + month)로 저장된다.
    """
    new_ts = state_updates.get("timestamp") or state.get("progress", {}).get("timestamp", "")
    ym = parse_ym(new_ts)
    if not ym:
        return
    current_months = ym[0] * 12 + ym[1]

    flags: dict = dict(state.get("flags") or {})
    decay_list: list[dict] = []

    for fid, faction in (state.get("factions") or {}).items():
        if not isinstance(faction, dict):
            continue
        if faction.get("defeated") or (faction.get("intel_level") or 0) <= 0:
            continue
        key  = f"intel_decay_{fid}_last"
        last = flags.get(key)
        if last is None:
            flags[key] = current_months
            continue
        if current_months - int(last) >= 6:
            decay_list.append({"id": fid, "delta": -1})
            flags[key] = current_months

    if decay_list:
        existing: dict[str, int] = {
            ic["id"]: ic["delta"]
            for ic in (state_updates.get("faction_intel_changes") or [])
            if isinstance(ic, dict) and ic.get("id")
        }
        for ic in decay_list:
            existing[ic["id"]] = existing.get(ic["id"], 0) + ic["delta"]
        state_updates["faction_intel_changes"] = [
            {"id": fid, "delta": d} for fid, d in existing.items()
        ]

    orig_flags = state.get("flags") or {}
    if flags != orig_flags:
        state_updates["flags_update"] = flags


def recompute_all_strengths(state: dict, state_updates: dict, tpp: int) -> None:
    """이번 턴 field_army 변화·거점 지배 변경을 반영해 strength_score를 전체 재계산합니다.

    결과는 state_updates["faction_strength_overrides"] = {fid: score} 로 저장된다.
    """
    factions: dict[str, dict] = {
        fid: dict(f) for fid, f in (state.get("factions") or {}).items()
        if isinstance(f, dict)
    }
    for fc in state_updates.get("faction_field_army_changes") or []:
        fid = fc.get("id") if isinstance(fc, dict) else None
        if fid and fid in factions and fc.get("delta") is not None:
            factions[fid]["field_army"] = max(
                0, (factions[fid].get("field_army") or 0) + int(fc["delta"])
            )

    locations: dict[str, dict] = {
        lid: dict(loc) for lid, loc in (state.get("locations") or {}).items()
        if isinstance(loc, dict)
    }
    for lc in state_updates.get("location_changes") or []:
        lid  = lc.get("id")         if isinstance(lc, dict) else None
        ctrl = lc.get("controller") if isinstance(lc, dict) else None
        if lid and lid in locations and ctrl and (ctrl == "contested" or ctrl in factions):
            locations[lid]["controller"] = ctrl

    state_updates["faction_strength_overrides"] = {
        fid: compute_faction_strength(faction, fid, locations, tpp)
        for fid, faction in factions.items()
    }
