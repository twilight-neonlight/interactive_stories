"""
engine/endgame.py — 승리/패배 조건 검사
"""
from engine.context import _event_condition_context
from engine.turn import parse_ym


def _eval_safe(condition: str, ctx: dict) -> bool:
    if not condition:
        return False
    try:
        return bool(eval(condition, {"__builtins__": {}}, ctx))
    except Exception:
        return False


def check_game_over(state: dict, scenario: dict, state_updates: dict) -> dict | None:
    """
    승리/패배 조건을 검사합니다.
    반환: {"type": "victory"|"defeat", "message": "..."} or None

    처리 순서:
    1. 전역 패배 — 주인공 사망
    2. 전역 패배 — 플레이어 세력 멸망
    3. 시나리오별 추가 패배 조건 (meta.json defeat_conditions)
    4. 시나리오 승리 조건 (meta.json victory_condition)
    """
    protagonist = state.get("protagonist")
    chars       = state.get("characters", {})
    facs        = state.get("factions", {})
    pc          = chars.get(protagonist, {})

    # ── 1. 주인공 사망 ───────────────────────────────────────────────────────
    if pc.get("status") == "dead":
        return {"type": "defeat", "message": "주인공이 사망했습니다."}
    for chg in (state_updates.get("character_status_changes") or []):
        if chg.get("id") == protagonist and chg.get("status") == "dead":
            return {"type": "defeat", "message": "주인공이 사망했습니다."}
    for entry in (state_updates.get("dead_characters") or []):
        cid = entry if isinstance(entry, str) else entry.get("id")
        if cid == protagonist:
            return {"type": "defeat", "message": "주인공이 사망했습니다."}

    # ── 2. 플레이어 세력 멸망 ────────────────────────────────────────────────
    pc_faction = pc.get("faction_id") or (protagonist if protagonist in facs else None)
    defeated_this_turn: set[str] = {
        f if isinstance(f, str) else f.get("id", "")
        for f in (state_updates.get("defeated_factions") or [])
        if f
    }
    if pc_faction:
        if pc_faction in defeated_this_turn or facs.get(pc_faction, {}).get("defeated"):
            return {"type": "defeat", "message": "주인공의 세력이 멸망했습니다."}

    # ── eval_ctx 구성: 이번 턴 패배 세력 반영 ────────────────────────────────
    new_ts = state_updates.get("timestamp") or state.get("progress", {}).get("timestamp", "")
    ym     = parse_ym(new_ts)
    year   = ym[0] if ym else None
    month  = ym[1] if ym else None

    # defeated_this_turn을 factions에 반영한 사본으로 eval_ctx 생성
    facs_updated = {
        fid: ({**f, "defeated": True} if fid in defeated_this_turn else f)
        for fid, f in facs.items()
    }
    eval_state = {**state, "factions": facs_updated}
    ctx = _event_condition_context(eval_state, year, month)

    # living_princes: defeated 제외한 경쟁 왕자 수 (victory 조건에서 사용)
    ctx["living_princes"] = sum(
        1 for fid, f in facs_updated.items()
        if f.get("type") == "faction"
        and not f.get("defeated")
        and fid != protagonist
    )

    # ── 3. 시나리오별 추가 패배 조건 ─────────────────────────────────────────
    for cond in (scenario.get("defeat_conditions") or []):
        if _eval_safe(cond.get("condition", ""), ctx):
            return {"type": "defeat", "message": cond.get("message", "패배했습니다.")}

    # ── 4. 승리 조건 ─────────────────────────────────────────────────────────
    if _eval_safe(scenario.get("victory_condition", ""), ctx):
        return {"type": "victory", "message": scenario.get("victory_message", "승리했습니다.")}

    return None
