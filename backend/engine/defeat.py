"""
engine/defeat.py — 세력 패퇴 자동 감지

수치 조건(전력 임계값 + 거점 상실)을 충족한 세력을 패퇴 처리하고,
이번 턴 state_updates를 반영한 임시 projection으로 사후 검사를 수행합니다.
"""

import copy
from engine.resolver import _get_player_faction_id


# 실효 전력(strength_score − battle_damage)이 이 값 미만이면 패퇴 후보
DEFEAT_STRENGTH_THRESHOLD = 30

# 이 유형들은 거점 보유 조건 없이 전력만으로 패퇴 처리
REMNANT_TYPES: frozenset[str] = frozenset({"rebels", "remnant"})


def auto_mark_defeated_factions(state: dict) -> list[str]:
    """수치 조건을 충족한 비플레이어 세력을 패퇴 처리합니다.

    - 일반 세력: 모든 거점 상실 + 실효 전력 < DEFEAT_STRENGTH_THRESHOLD
    - rebels/remnant: 거점 조건 면제, 실효 전력 < 임계값이면 즉시 패퇴

    세력 객체는 삭제하지 않고 defeated 플래그만 세운다.
    반환: 이번 호출에서 새로 패퇴 처리된 faction id 목록
    """
    factions  = state.get("factions", {})
    locations = state.get("locations", {})
    if not isinstance(factions, dict):
        return []

    # 거점을 하나라도 보유한 세력 집합
    has_location: set[str] = set()
    for loc in locations.values():
        ctrl = loc.get("controller")
        if ctrl and ctrl != "contested":
            has_location.add(ctrl)

    player_fid = _get_player_faction_id(state)
    defeated: list[str] = []
    for fid, faction in factions.items():
        if fid == player_fid or not isinstance(faction, dict) or faction.get("defeated"):
            continue
        effective = (faction.get("strength_score") or 0) - (faction.get("battle_damage") or 0)
        if effective >= DEFEAT_STRENGTH_THRESHOLD:
            continue
        is_remnant = faction.get("type", "") in REMNANT_TYPES
        if is_remnant or fid not in has_location:
            faction["defeated"] = True
            defeated.append(fid)
    return defeated


def merge_defeated_factions_update(updates: dict, defeated_ids: list[str]) -> None:
    """auto_mark_defeated_factions 결과를 state_updates["defeated_factions"]에 병합합니다."""
    if not defeated_ids:
        return
    existing = list(updates.get("defeated_factions") or [])
    seen = set(existing)
    for fid in defeated_ids:
        if fid not in seen:
            existing.append(fid)
            seen.add(fid)
    updates["defeated_factions"] = existing


def project_state_updates_for_defeat(state: dict, updates: dict) -> dict:
    """이번 응답의 전력 변경을 반영한 임시 state를 만들어 자동 패퇴를 검사합니다.

    deepcopy 후 updates의 전력·거점 변경분을 투영(projection)해
    사후 auto_mark_defeated_factions 호출에 사용할 상태를 반환합니다.
    """
    projected = copy.deepcopy(state)
    factions  = projected.get("factions", {})
    if not isinstance(factions, dict):
        return projected

    for f in updates.get("new_factions") or []:
        fid = f.get("id") if isinstance(f, dict) else None
        if fid and fid not in factions:
            factions[fid] = {**f, "battle_damage": f.get("battle_damage", 0)}

    for fid in updates.get("defeated_factions") or []:
        if fid in factions:
            factions[fid]["defeated"] = True

    for fid, new_score in (updates.get("faction_strength_overrides") or {}).items():
        if fid in factions:
            factions[fid]["strength_score"] = new_score

    for fc in updates.get("faction_battle_damage") or []:
        fid = fc.get("id") if isinstance(fc, dict) else None
        if fid in factions and fc.get("damage") is not None:
            factions[fid]["battle_damage"] = (
                (factions[fid].get("battle_damage") or 0) + abs(fc["damage"])
            )

    for fc in updates.get("faction_battle_recovery") or []:
        fid = fc.get("id") if isinstance(fc, dict) else None
        if fid in factions and fc.get("amount") is not None:
            factions[fid]["battle_damage"] = max(
                0, (factions[fid].get("battle_damage") or 0) - abs(fc["amount"])
            )

    proj_locs = projected.get("locations", {})
    proj_facs = projected.get("factions", {})
    for lc in updates.get("location_changes") or []:
        lid  = lc.get("id")         if isinstance(lc, dict) else None
        ctrl = lc.get("controller") if isinstance(lc, dict) else None
        if lid and lid in proj_locs and ctrl and (ctrl == "contested" or ctrl in proj_facs):
            proj_locs[lid]["controller"] = ctrl

    return projected
