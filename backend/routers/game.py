"""
routers/game.py — 오프닝·턴 처리 API
"""

import asyncio
import re
from fastapi import APIRouter
from pydantic import BaseModel

from config          import SYSTEM_PROMPT
from gemini_client   import call_gemini
from scenarios_loader import SCENARIOS, GARRISON_POINTS_BY_TIER
from engine.resolver import (
    resolve_action, resolution_prompt, needs_resolution, classify_action_type,
    init_combat_phase, advance_combat_phase, resolve_retreat,
    combat_prep_prompt, combat_ongoing_prompt, combat_end_prompt,
    calc_stat_modifier, _MIN_PHASES_BEFORE_VICTOR,
)
from engine.classifier import classify_action_llm, CLS_TO_RESOLVER
from engine.quality    import evaluate_action_quality
from engine.turn       import turn_engine, extract_state_update, extract_timestamp
from engine.context    import (
    build_scenario_context, build_opening_context, OPENING_INSTRUCTION,
    compute_event_states, detect_event_transitions, build_event_transition_prompt,
    collect_transition_effects, strip_event_states,
)


_ACTION_STAT_KEY: dict[str, str] = {
    'military':   '통솔',
    'defense':    '통솔',
    'surprise':   '지략',
    'diplomatic': '외교',
    'intrigue':   '지략',
}

# 점령지 처분 유형별 효과
# base: 점령 직후 garrison_modifier 초기값
# recovery_ratio: base_pts 기준 야전군 battle_damage 회복 비율
_CONQUEST_DISPOSITIONS: dict[str, dict] = {
    "초토화":      {"base": 0.1, "recovery_ratio": 0.30},
    "약탈":        {"base": 0.2, "recovery_ratio": 0.15},
    "피해 최소화": {"base": 0.3, "recovery_ratio": 0.05},
}

# garrison_modifier 월간 회복량 (처분 확정 후 매 게임 내 월마다 적용)
_GARRISON_RECOVERY_PER_MONTH = 0.03


def _classify_conquest_disposition(command: str) -> str | None:
    """명령어에서 점령지 처분 유형을 추출합니다."""
    if "초토화" in command:
        return "초토화"
    if "약탈" in command:
        return "약탈"
    if "피해" in command or "최소화" in command or "보호" in command:
        return "피해 최소화"
    return None


def _build_modifiers(*mods) -> list[tuple[str, int]] | None:
    """None 제거 후 수정치 리스트 반환. 빈 경우 None."""
    result = [m for m in mods if m is not None]
    return result if result else None


async def _async_none():
    return None


# ── garrison 유틸 ─────────────────────────────────────────────────────────────

def _parse_ym(ts: str) -> tuple[int, int] | None:
    """타임스탬프 문자열에서 (year, month) 추출. 월 정보 없으면 None."""
    m = re.search(r'(\d{3,4})년\s*(\d{1,2})월', ts)
    return (int(m.group(1)), int(m.group(2))) if m else None


def _ts_ym_only(ts: str) -> str:
    """타임스탬프에서 연도·월만 추출합니다."""
    m = re.search(r'(\d{3,4})년\s*(\d{1,2})월', ts)
    return f"{m.group(1)}년 {m.group(2)}월" if m else ts


def _get_scenario_tpp(state: dict) -> int | None:
    scenario_id = state.get("scenarioId", "")
    s = next((s for s in SCENARIOS if s["id"] == scenario_id), None)
    return s.get("troops_per_strength_point") if s else None


def _apply_garrison_updates(state: dict, new_ts: str, tpp: int, loc_change_map: dict) -> list[dict]:
    """garrison 관련 location_changes를 loc_change_map에 in-place로 병합합니다.

    처리 순서:
    1. 이번 턴 controller 변경 거점 → garrison_modifier=0.3(임시), conquered_at=new_ts 기록
    2. conquered_at이 있는 미점령 거점 → 경과 시간 기반 모디파이어 재계산

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
            lc["conquered_at"]      = _ts_ym_only(new_ts)
            tier     = old_locations.get(lid, {}).get("tier", "")
            base_pts = GARRISON_POINTS_BY_TIER.get(tier, 0)
            lc["garrison"] = round(base_pts * 0.3 * tpp)
            newly_pending.append({
                "id":          lid,
                "tier":        tier,
                "name":        old_locations.get(lid, {}).get("name", lid),
                "conquered_at": lc["conquered_at"],
            })

    # 2. 처분이 확정된 점령 거점 회복
    # garrison_modifier(t) = base + elapsed_months × 0.03
    # base = 처분 유형(conquest_disposition)에서 결정, _CONQUEST_DISPOSITIONS 참조
    new_ym = _parse_ym(new_ts)
    for lid, loc in old_locations.items():
        if lid in loc_change_map:
            continue
        conquered_at        = loc.get("conquered_at")
        conquest_disposition = loc.get("conquest_disposition")
        if not conquered_at or not conquest_disposition:
            continue
        cym = _parse_ym(conquered_at)
        if not cym or not new_ym:
            continue
        elapsed  = (new_ym[0] - cym[0]) * 12 + (new_ym[1] - cym[1])
        base     = _CONQUEST_DISPOSITIONS.get(conquest_disposition, {}).get("base", 0.3)
        new_mod  = min(1.0, base + max(0, elapsed) * _GARRISON_RECOVERY_PER_MONTH)
        tier     = loc.get("tier", "")
        base_pts = GARRISON_POINTS_BY_TIER.get(tier, 0)
        change: dict = {
            "id":               lid,
            "garrison_modifier": round(new_mod, 4),
            "garrison":          round(base_pts * new_mod * tpp),
        }
        if new_mod >= 1.0:
            change["conquered_at"]        = None
            change["conquest_disposition"] = None
            change["garrison_modifier"]    = 1.0
        loc_change_map[lid] = change

    return newly_pending


router = APIRouter()


class Message(BaseModel):
    role: str
    content: str


class TurnRequest(BaseModel):
    command: str
    state:   dict
    history: list[Message]
    retreat: bool = False


class OpeningRequest(BaseModel):
    state: dict


def _get_scenario_prompts(state: dict) -> dict:
    scenario_id   = state.get("scenarioId", "")
    scenario_data = next((s for s in SCENARIOS if s["id"] == scenario_id), None)
    return scenario_data.get("scenario_prompts", {}) if scenario_data else {}


@router.post("/api/opening")
async def generate_opening(req: OpeningRequest):
    scenario_prompts = _get_scenario_prompts(req.state)
    full_system = (SYSTEM_PROMPT
                   + build_scenario_context(req.state, scenario_prompts=scenario_prompts)
                   + build_opening_context(req.state)
                   + OPENING_INSTRUCTION)
    content = await call_gemini([
        {"role": "system", "content": full_system},
        {"role": "user",   "content": "[게임 시작] 오프닝 장면을 생성하라."},
    ])
    content, extra = extract_state_update(content)
    # 오프닝: 이벤트 상태 초기화 (트리거 알림 없이 조용히 active 설정)
    initial_event_states = strip_event_states(compute_event_states(req.state))
    return {
        "content":       content,
        "timestamp":     extract_timestamp(content),
        "state_updates": {
            "new_characters":      extra.get("new_characters", []),
            "event_state_changes": initial_event_states,
        },
    }


@router.post("/api/turn")
async def process_turn(req: TurnRequest):
    combat_state_in  = req.state.get("combatState")
    quality_mod      = None
    new_combat_state = None

    # 점령지 처분 대기 확인 (LLM 호출 전에 command를 분석해야 하므로 최상단에서 처리)
    pending_dispositions: list[dict] = req.state.get("pendingConquestDispositions") or []
    disposition_type: str | None = (
        _classify_conquest_disposition(req.command) if pending_dispositions else None
    )

    if combat_state_in and combat_state_in.get("active"):
        # ── 전투 진행 중 ──────────────────────────────────────────────────────
        if req.retreat:
            resolution, new_combat_state = resolve_retreat(req.state)
            sys_prompt_tail = combat_end_prompt(new_combat_state, resolution)
        else:
            combat_action_type = classify_action_type(req.command)
            if combat_action_type not in ("military", "surprise", "defense"):
                combat_action_type = "military"
            quality_mod = await evaluate_action_quality(req.command, req.state, combat_action_type)
            stat_key    = _ACTION_STAT_KEY.get(combat_action_type, '통솔')
            enemy_fid   = combat_state_in.get("enemy_faction_id")
            stat_mod    = calc_stat_modifier(req.state, stat_key, enemy_fid)
            resolution, new_combat_state = advance_combat_phase(
                req.command, req.state, _build_modifiers(quality_mod, stat_mod)
            )
            if new_combat_state.get("ended"):
                sys_prompt_tail = combat_end_prompt(new_combat_state, resolution)
            else:
                completed_phase = new_combat_state.get("phase_number", 2) - 1
                sys_prompt_tail = combat_ongoing_prompt(completed_phase, new_combat_state, resolution)
    else:
        # ── 일반 턴 ───────────────────────────────────────────────────────────
        kw_type = classify_action_type(req.command)

        cls, quality_mod = await asyncio.gather(
            classify_action_llm(req.command, req.state),
            evaluate_action_quality(req.command, req.state, kw_type)
            if needs_resolution(req.command) else _async_none(),
        )

        cls_type      = cls.get("type", "general")
        resolver_type = CLS_TO_RESOLVER.get(cls_type, "general")
        target_fid    = cls.get("target_faction_id")

        if cls_type in ("open_field", "ambush", "siege_attack"):
            stat_key = _ACTION_STAT_KEY.get(resolver_type, '통솔')
            stat_mod = calc_stat_modifier(req.state, stat_key, target_fid)
            resolution, new_combat_state = init_combat_phase(
                req.command, req.state,
                _build_modifiers(stat_mod), classification=cls
            )
            sys_prompt_tail = combat_prep_prompt(new_combat_state, resolution)
        else:
            stat_key = _ACTION_STAT_KEY.get(resolver_type)
            stat_mod = calc_stat_modifier(req.state, stat_key, target_fid) if stat_key else None
            resolution = resolve_action(
                req.command, req.state,
                extra_modifiers=_build_modifiers(quality_mod, stat_mod),
                action_type=resolver_type,
            )
            sys_prompt_tail = resolution_prompt(resolution)

    # 이벤트 전환 감지
    stored_event_states  = req.state.get("eventStates", {})
    current_event_states = compute_event_states(req.state)
    newly_active, newly_ended = detect_event_transitions(
        stored_event_states, current_event_states, req.state.get("events", [])
    )
    event_transition_prompt = build_event_transition_prompt(
        newly_active, newly_ended, req.state.get("protagonist")
    )

    scenario_prompts = _get_scenario_prompts(req.state)
    full_system = (SYSTEM_PROMPT
                   + build_scenario_context(req.state, scenario_prompts=scenario_prompts)
                   + sys_prompt_tail
                   + event_transition_prompt)

    # 처분 프롬프트 — LLM에 서술 방향 전달
    if pending_dispositions:
        loc_list = ", ".join(pd.get("name", pd["id"]) for pd in pending_dispositions)
        if disposition_type:
            full_system += (
                f"\n\n## 점령지 처분 진행\n"
                f"플레이어가 {loc_list}의 처분 방식을 결정하는 중이다. "
                f"선택의 구체적 결과(약탈의 혼란, 초토화의 파괴, 혹은 절제된 입성 등)를 "
                f"생생하게 서술하고, 이 결정이 통치·민심·외교에 미칠 파급을 간략히 시사하라."
            )
        else:
            full_system += (
                f"\n\n## 점령지 처분 대기\n"
                f"{loc_list}의 처분이 아직 결정되지 않았다. "
                f"서술 말미에 처분 선택지를 다시 제시하라: 초토화 / 약탈 / 피해 최소화."
            )

    messages  = [{"role": "system", "content": full_system}]
    messages += [{"role": m.role, "content": m.content} for m in req.history]
    messages.append({"role": "user", "content": req.command})

    content = await call_gemini(messages)
    content, extra = extract_state_update(content)
    state_updates  = turn_engine(content, req.state)

    # STATE_UPDATE 명시값이 있으면 텍스트 파싱(turn_engine) 결과 대체
    if isinstance(extra.get("scene"),   int) and extra["scene"]   >= 1:
        state_updates["scene"] = extra["scene"]
    if isinstance(extra.get("chapter"), int) and extra["chapter"] >= 1:
        state_updates["chapter"] = extra["chapter"]
    if isinstance(extra.get("is_chapter_end"), bool):
        state_updates["is_chapter_end"] = extra["is_chapter_end"]

    in_combat = bool(combat_state_in and combat_state_in.get("active"))
    for key in ("new_characters", "dead_characters", "new_factions", "defeated_factions",
                "faction_strength_changes", "faction_battle_recovery",
                "faction_diplomacy_changes",
                "character_troop_changes", "character_disposition_changes", "character_title_changes",
                "faction_intel_changes", "new_locations", "location_changes",
                "player_location_id"):
        if extra.get(key):
            state_updates[key] = extra[key]

    # 전투 페이즈 밖에서만 LLM의 faction_battle_damage를 수용
    if not in_combat and extra.get("faction_battle_damage"):
        state_updates["faction_battle_damage"] = extra["faction_battle_damage"]

    if isinstance(extra.get("weather"), str):
        state_updates["weather"] = extra["weather"]

    state_updates["event_state_changes"] = strip_event_states(current_event_states)

    # 주둔군 갱신 (controller 변경 → conquered_at 기록, 기존 점령지 시간 경과 회복)
    tpp = _get_scenario_tpp(req.state)
    newly_pending: list[dict] = []
    if tpp:
        new_ts = state_updates.get("timestamp") or req.state.get("progress", {}).get("timestamp", "")
        loc_change_map: dict[str, dict] = {
            lc["id"]: lc for lc in (state_updates.get("location_changes") or [])
        }
        newly_pending = _apply_garrison_updates(req.state, new_ts, tpp, loc_change_map)
        if loc_change_map:
            state_updates["location_changes"] = list(loc_change_map.values())

    # 이전 턴 점령지 처분 적용
    unresolved: list[dict] = []
    if pending_dispositions:
        if disposition_type:
            info           = _CONQUEST_DISPOSITIONS[disposition_type]
            new_mod        = info["base"]
            recovery_ratio = info["recovery_ratio"]

            existing_lcs: dict[str, dict] = {
                lc["id"]: lc for lc in (state_updates.get("location_changes") or [])
            }
            protagonist_fid = req.state.get("protagonist")
            total_recovery  = 0

            for pd in pending_dispositions:
                lid      = pd["id"]
                tier     = pd.get("tier", "")
                base_pts = GARRISON_POINTS_BY_TIER.get(tier, 0)
                if lid not in existing_lcs:
                    existing_lcs[lid] = {"id": lid}
                # garrison_modifier: base (점령 직후 0개월 경과)
                existing_lcs[lid]["garrison_modifier"]    = new_mod
                existing_lcs[lid]["conquest_disposition"] = disposition_type
                if tpp:
                    existing_lcs[lid]["garrison"] = round(base_pts * new_mod * tpp)
                total_recovery += round(base_pts * recovery_ratio)

            state_updates["location_changes"] = list(existing_lcs.values())

            if protagonist_fid and total_recovery > 0:
                recovery_list = list(state_updates.get("faction_battle_recovery") or [])
                recovery_list.append({"id": protagonist_fid, "amount": total_recovery})
                state_updates["faction_battle_recovery"] = recovery_list
        else:
            unresolved = pending_dispositions  # 미결 처분 유지

    state_updates["pending_conquest_dispositions"] = unresolved + newly_pending

    # 시스템 이벤트 효과 (LLM 불필요) — LLM 결과 뒤에 병합해 시스템 값이 우선
    event_effects = collect_transition_effects(newly_active, newly_ended, req.state, req.state.get("protagonist"))
    for key, val in event_effects.items():
        state_updates[key] = state_updates.get(key) or []
        state_updates[key] = state_updates[key] + val

    if new_combat_state is not None:
        for key in ("player_coalition", "enemy_coalition"):
            if isinstance(extra.get(key), list):
                new_combat_state[key] = extra[key]

        # 전투 지명·연도: 개시 씬에서만 LLM이 제공
        if isinstance(extra.get("battle_location"), str):
            new_combat_state["battle_location_name"] = extra["battle_location"]
        if isinstance(extra.get("battle_year"), str):
            new_combat_state["battle_year"] = extra["battle_year"]

        # 적 예고 행동: LLM이 이번 장면에서 제시한 다음 페이즈 적 행동 저장
        if isinstance(extra.get("enemy_next_action"), str):
            new_combat_state["enemy_next_action"] = extra["enemy_next_action"]

        # LLM이 서술로 전투 종결을 선언한 경우 (최소 교전 횟수 이후만 수용)
        completed_phase = new_combat_state.get("phase_number", 2) - 1
        if not new_combat_state.get("ended") and not req.retreat:
            victor = extra.get("combat_victor") if completed_phase >= _MIN_PHASES_BEFORE_VICTOR else None
            if victor == "player":
                new_combat_state.update({
                    "active": False, "ended": True,
                    "winner": "player", "final_tier": "성공", "final_tier_en": "success",
                })
            elif victor == "enemy":
                new_combat_state.update({
                    "active": False, "ended": True,
                    "winner": "enemy", "final_tier": "실패", "final_tier_en": "failure",
                })

        state_updates["combat_state"] = new_combat_state
        if new_combat_state.get("ended"):
            pending = new_combat_state.get("pending_battle_damage", {})
            state_updates["faction_battle_damage"] = [
                {"id": fid, "damage": dmg} for fid, dmg in pending.items() if dmg > 0
            ]
            # 전투 패배 이력 누적 — 이벤트 조건 평가에서 lost_to_{fid}로 참조
            if new_combat_state.get("winner") == "enemy":
                enemy_fid = new_combat_state.get("enemy_faction_id")
                if enemy_fid:
                    existing = req.state.get("lostBattles") or {}
                    state_updates["lost_battles"] = {**existing, enemy_fid: True}

    return {
        "content":      content,
        "state_updates": state_updates,
        "resolution":   resolution,
        "_debug": {
            "state_update": extra,
            "quality_mod":  quality_mod,
        },
    }
