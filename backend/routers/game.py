"""
routers/game.py — 오프닝·턴 처리 API

HTTP 요청 수신 → 엔진 호출 → 응답 반환을 담당합니다.
"""

import asyncio
import copy
from fastapi import APIRouter
from pydantic import BaseModel

from config          import SYSTEM_PROMPT
from gemini_client   import call_gemini
from scenarios_loader import (
    SCENARIOS,
    GARRISON_POINTS_BY_TIER,
    CONQUEST_DISPOSITIONS,
    get_scenario_tpp,
    get_scenario_reserve_divisor,
)
from engine.resolver import (
    resolve_action, resolution_prompt, classify_action_type,
    init_combat_phase, advance_combat_phase, resolve_retreat,
    combat_prep_prompt, combat_ongoing_prompt, combat_end_prompt,
    init_diplomacy_session, advance_diplomacy_session, resolve_diplomacy_withdrawal,
    diplomacy_prep_prompt, diplomacy_ongoing_prompt, diplomacy_end_prompt,
    calc_stat_modifier, calc_diplomacy_relation_modifier, calc_admin_recovery_multiplier,
    _get_player_faction_id,
    _MIN_PHASES_BEFORE_VICTOR,
    roll_battle_weather,
)
from engine.classifier import classify_action_llm, CLS_TO_RESOLVER
from engine.quality    import evaluate_action_quality
from engine.turn       import turn_engine, extract_state_update, extract_timestamp
from engine.context    import (
    build_scenario_context, build_opening_context, OPENING_INSTRUCTION,
    compute_event_states, detect_event_transitions, build_event_transition_prompt,
    collect_transition_effects, strip_event_states,
)
from engine.fiscal  import compute_player_fiscal, auto_treasury_update
from engine.conquest import classify_conquest_disposition, apply_garrison_updates
from engine.tick    import (
    auto_battle_damage_recovery,
    auto_reserve_recovery,
    auto_intel_decay,
    recompute_all_strengths,
)
from engine.defeat  import (
    auto_mark_defeated_factions,
    merge_defeated_factions_update,
    project_state_updates_for_defeat,
)


# ── 라우팅 상수 ───────────────────────────────────────────────────────────────

_ACTION_STAT_KEY: dict[str, str] = {
    'military':   '통솔',
    'defense':    '통솔',
    'surprise':   '지략',
    'diplomatic': '외교',
    'intrigue':   '지략',
}

_FRONTEND_TO_RESOLVER: dict[str, str] = {
    "attack":     "military",
    "surprise":   "surprise",
    "defense":    "defense",
    "siege":      "military",
    "diplomatic": "diplomatic",
    "intrigue":   "intrigue",
    "passive":    "passive",
}


# ── 유틸 ──────────────────────────────────────────────────────────────────────

def _build_modifiers(*mods) -> list[tuple[str, int]] | None:
    """None 제거 후 수정치 리스트 반환. 빈 경우 None."""
    result = [m for m in mods if m is not None]
    return result if result else None


async def _async_none():
    return None


def _get_scenario_prompts(state: dict) -> dict:
    scenario_data = next((s for s in SCENARIOS if s["id"] == state.get("scenarioId", "")), None)
    return scenario_data.get("scenario_prompts", {}) if scenario_data else {}


# ── 요청 모델 ─────────────────────────────────────────────────────────────────

router = APIRouter()


class Message(BaseModel):
    role: str
    content: str


class TurnRequest(BaseModel):
    command:     str
    state:       dict
    history:     list[Message]
    retreat:     bool = False
    withdraw:    bool = False
    action_type: str | None = None


class OpeningRequest(BaseModel):
    state: dict


# ── 엔드포인트 ────────────────────────────────────────────────────────────────

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
    state = copy.deepcopy(req.state)
    auto_defeated_at_start = auto_mark_defeated_factions(state)

    diplomacy_state_in  = state.get("diplomacyState")
    combat_state_in     = state.get("combatState")
    quality_mod         = None
    new_combat_state    = None
    new_diplomacy_state = None

    # 점령지 처분 대기 확인 (LLM 호출 전에 command를 분석해야 하므로 최상단에서 처리)
    pending_dispositions: list[dict] = state.get("pendingConquestDispositions") or []
    disposition_type: str | None = (
        classify_conquest_disposition(req.command) if pending_dispositions else None
    )

    if diplomacy_state_in and diplomacy_state_in.get("active"):
        # ── 외교 회담 진행 중 ────────────────────────────────────────────────
        if req.withdraw:
            resolution, new_diplomacy_state = resolve_diplomacy_withdrawal(state)
            sys_prompt_tail = diplomacy_end_prompt(new_diplomacy_state)
        else:
            target_fid  = diplomacy_state_in.get("target_faction_id")
            old_stance  = diplomacy_state_in.get("opponent_next_stance")
            quality_mod = await evaluate_action_quality(req.command, state, "diplomatic")
            stat_mod    = calc_stat_modifier(state, "외교", target_fid)
            dipl_mod    = calc_diplomacy_relation_modifier(state, target_fid)
            resolution, new_diplomacy_state = advance_diplomacy_session(
                req.command, state, _build_modifiers(quality_mod, stat_mod, dipl_mod)
            )
            sys_prompt_tail = diplomacy_ongoing_prompt(
                new_diplomacy_state, resolution, old_stance=old_stance
            )

    elif combat_state_in and combat_state_in.get("active"):
        # ── 전투 진행 중 ──────────────────────────────────────────────────────
        if req.retreat:
            resolution, new_combat_state = resolve_retreat(state)
            sys_prompt_tail = combat_end_prompt(new_combat_state, resolution)
        else:
            _hint = _FRONTEND_TO_RESOLVER.get(req.action_type or "", "")
            if _hint in ("military", "surprise", "defense"):
                combat_action_type = _hint
            else:
                combat_action_type = classify_action_type(req.command)
                if combat_action_type not in ("military", "surprise", "defense"):
                    combat_action_type = "military"
            quality_mod = await evaluate_action_quality(req.command, state, combat_action_type)
            stat_key    = _ACTION_STAT_KEY.get(combat_action_type, '통솔')
            enemy_fid   = combat_state_in.get("enemy_faction_id")
            stat_mod    = calc_stat_modifier(state, stat_key, enemy_fid)
            resolution, new_combat_state = advance_combat_phase(
                req.command, state, _build_modifiers(quality_mod, stat_mod)
            )
            if new_combat_state.get("ended"):
                sys_prompt_tail = combat_end_prompt(new_combat_state, resolution)
            else:
                completed_phase = new_combat_state.get("phase_number", 2) - 1
                sys_prompt_tail = combat_ongoing_prompt(completed_phase, new_combat_state, resolution)
    else:
        # ── 일반 턴 ───────────────────────────────────────────────────────────
        kw_type = _FRONTEND_TO_RESOLVER.get(req.action_type or "", "") or classify_action_type(req.command)
        _needs_res = kw_type not in ("passive", "general")

        cls, quality_mod = await asyncio.gather(
            classify_action_llm(req.command, state),
            evaluate_action_quality(req.command, state, kw_type)
            if _needs_res else _async_none(),
        )

        cls_type      = cls.get("type", "general")
        resolver_type = CLS_TO_RESOLVER.get(cls_type, "general")
        target_fid    = cls.get("target_faction_id")

        if cls_type == "diplomatic_session":
            stat_mod = calc_stat_modifier(state, "외교", target_fid)
            dipl_mod = calc_diplomacy_relation_modifier(state, target_fid)
            resolution, new_diplomacy_state = init_diplomacy_session(
                req.command, state,
                _build_modifiers(quality_mod, stat_mod, dipl_mod),
                classification=cls,
            )
            sys_prompt_tail = diplomacy_prep_prompt(new_diplomacy_state, resolution)
        elif cls_type in ("open_field", "ambush", "siege_attack"):
            stat_key = _ACTION_STAT_KEY.get(resolver_type, '통솔')
            stat_mod = calc_stat_modifier(state, stat_key, target_fid)
            resolution, new_combat_state = init_combat_phase(
                req.command, state,
                _build_modifiers(stat_mod), classification=cls
            )
            sys_prompt_tail = combat_prep_prompt(new_combat_state)
        else:
            stat_key  = _ACTION_STAT_KEY.get(resolver_type)
            stat_mod  = calc_stat_modifier(state, stat_key, target_fid) if stat_key else None
            dipl_mod  = calc_diplomacy_relation_modifier(state, target_fid) if resolver_type == "diplomatic" else None
            resolution = resolve_action(
                req.command, state,
                extra_modifiers=_build_modifiers(quality_mod, stat_mod, dipl_mod),
                action_type=resolver_type,
            )
            sys_prompt_tail = resolution_prompt(resolution)

    # 이벤트 전환 감지
    stored_event_states  = state.get("eventStates", {})
    current_event_states = compute_event_states(state)
    newly_active, newly_ended = detect_event_transitions(
        stored_event_states, current_event_states, state.get("events", [])
    )
    event_transition_prompt = build_event_transition_prompt(
        newly_active, newly_ended, state.get("protagonist")
    )
    auto_defeat_prompt = ""
    if auto_defeated_at_start:
        factions = state.get("factions", {})
        names = ", ".join(
            factions.get(fid, {}).get("name", fid) for fid in auto_defeated_at_start
        )
        auto_defeat_prompt = (
            "\n\n---\n## 자동 패퇴 감지 (서술 반영)\n"
            f"거점 상실·전력 소진 조건을 충족해 패퇴 처리된 세력이 확인됐다: {names}. "
            "이번 응답에서 이 세력의 전멸·해체 소식이 정보원, 전령, 피난민, 포로 심문 등 "
            "개연성 있는 경로로 플레이어에게 전달되도록 간략히 반영하라."
        )

    scenario_prompts = _get_scenario_prompts(state)
    full_system = (SYSTEM_PROMPT
                   + build_scenario_context(state, scenario_prompts=scenario_prompts)
                   + sys_prompt_tail
                   + auto_defeat_prompt
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
    state_updates  = turn_engine(content, state)
    merge_defeated_factions_update(state_updates, auto_defeated_at_start)

    in_combat = bool(combat_state_in and combat_state_in.get("active"))
    for key in ("new_characters", "dead_characters", "new_factions", "defeated_factions",
                "faction_field_army_changes", "faction_reserve_changes",
                "faction_diplomacy_changes",
                "character_troop_changes", "character_disposition_changes", "character_title_changes",
                "faction_intel_changes", "new_locations", "location_changes",
                "player_location_id",
                "faction_income_changes", "treasury_changes"):
        if extra.get(key):
            state_updates[key] = extra[key]

    # 전투 페이즈 밖에서만 LLM의 faction_battle_damage를 수용
    if not in_combat and extra.get("faction_battle_damage"):
        state_updates["faction_battle_damage"] = extra["faction_battle_damage"]

    if isinstance(extra.get("weather"), str):
        state_updates["weather"] = extra["weather"]

    # 주둔군 갱신 (controller 변경 → conquered_at 기록, 기존 점령지 시간 경과 회복)
    tpp     = get_scenario_tpp(state)
    res_div = get_scenario_reserve_divisor(state)

    # 재정 상태 계산 (이번 턴 회복·누적에 사용)
    fiscal_info = compute_player_fiscal(state, tpp, res_div) if tpp else None
    fiscal_mult = fiscal_info["fiscal_mult"] if fiscal_info else 1.0

    newly_pending: list[dict] = []
    if tpp:
        new_ts = state_updates.get("timestamp") or state.get("progress", {}).get("timestamp", "")
        loc_change_map: dict[str, dict] = {
            lc["id"]: lc for lc in (state_updates.get("location_changes") or [])
        }
        admin_mult    = calc_admin_recovery_multiplier(state)
        newly_pending = apply_garrison_updates(
            state, new_ts, tpp, loc_change_map, admin_mult, fiscal_mult
        )
        if loc_change_map:
            state_updates["location_changes"] = list(loc_change_map.values())

    # 이전 턴 점령지 처분 적용
    unresolved: list[dict] = []
    if pending_dispositions:
        if disposition_type:
            info           = CONQUEST_DISPOSITIONS[disposition_type]
            new_mod        = info["base"]
            recovery_ratio = info["recovery_ratio"]

            existing_lcs: dict[str, dict] = {
                lc["id"]: lc for lc in (state_updates.get("location_changes") or [])
            }
            protagonist_fid = _get_player_faction_id(state)
            total_recovery  = 0

            for pd in pending_dispositions:
                lid      = pd["id"]
                tier     = pd.get("tier", "")
                base_pts = GARRISON_POINTS_BY_TIER.get(tier, 0)
                if lid not in existing_lcs:
                    existing_lcs[lid] = {"id": lid}
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

    auto_battle_damage_recovery(state, state_updates)
    auto_reserve_recovery(state, state_updates, fiscal_mult)
    auto_treasury_update(state, state_updates, fiscal_info)
    auto_intel_decay(state, state_updates)
    if tpp:
        recompute_all_strengths(state, state_updates, tpp)

    if new_diplomacy_state is not None:
        if isinstance(extra.get("opponent_next_stance"), str):
            new_diplomacy_state["opponent_next_stance"] = extra["opponent_next_stance"]
        if not new_diplomacy_state.get("ended"):
            outcome = extra.get("diplomacy_outcome")
            if outcome in ("agreement", "breakdown"):
                new_diplomacy_state.update({
                    "active":  False,
                    "ended":   True,
                    "outcome": outcome,
                })
        state_updates["diplomacy_state"] = new_diplomacy_state

    if new_combat_state is not None:
        for key in ("player_coalition", "enemy_coalition"):
            if isinstance(extra.get(key), list):
                new_combat_state[key] = extra[key]

        if isinstance(extra.get("battle_location"), str):
            new_combat_state["battle_location_name"] = extra["battle_location"]
        if isinstance(extra.get("battle_year"), str):
            new_combat_state["battle_year"] = extra["battle_year"]
        if isinstance(extra.get("battle_terrain"), str):
            terrain = extra["battle_terrain"]
            new_combat_state["battle_terrain"] = terrain
            if new_combat_state.get("phase_number", 1) == 1 and not isinstance(extra.get("weather"), str):
                state_updates["weather"] = roll_battle_weather(terrain)

        if isinstance(extra.get("enemy_next_action"), str):
            new_combat_state["enemy_next_action"] = extra["enemy_next_action"]

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
            if new_combat_state.get("winner") == "enemy":
                enemy_fid = new_combat_state.get("enemy_faction_id")
                if enemy_fid:
                    existing = state.get("lostBattles") or {}
                    state_updates["lost_battles"] = {**existing, enemy_fid: True}

    # 시스템 이벤트 효과 적용
    event_effects = collect_transition_effects(newly_active, newly_ended, state, state.get("protagonist"))
    for key, val in event_effects.items():
        state_updates[key] = state_updates.get(key) or []
        state_updates[key] = state_updates[key] + val

    projected_state = project_state_updates_for_defeat(state, state_updates)
    auto_defeated_after_updates = auto_mark_defeated_factions(projected_state)
    merge_defeated_factions_update(state_updates, auto_defeated_after_updates)
    state_updates["event_state_changes"] = strip_event_states(current_event_states)

    return {
        "content":      content,
        "state_updates": state_updates,
        "resolution":   resolution,
        "_debug": {
            "state_update": extra,
            "quality_mod":  quality_mod,
        },
    }
