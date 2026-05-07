"""
routers/game.py — 오프닝·턴 처리 API
"""

import asyncio
from fastapi import APIRouter
from pydantic import BaseModel

from config          import SYSTEM_PROMPT
from gemini_client   import call_gemini
from scenarios_loader import SCENARIOS
from engine.resolver import (
    resolve_action, resolution_prompt, needs_resolution, classify_action_type,
    init_combat_phase, advance_combat_phase, resolve_retreat,
    combat_prep_prompt, combat_ongoing_prompt, combat_end_prompt,
    calc_phase_damage, combat_damage_labels, _MIN_PHASES_BEFORE_VICTOR,
)
from engine.classifier import classify_action_llm, CLS_TO_RESOLVER
from engine.quality    import evaluate_action_quality
from engine.turn       import turn_engine, extract_state_update, extract_timestamp
from engine.context    import build_scenario_context, build_opening_npc_context, OPENING_INSTRUCTION


async def _async_none():
    return None

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


@router.post("/api/opening")
async def generate_opening(req: OpeningRequest):
    scenario_id   = req.state.get("scenarioId", "")
    scenario_data = next((s for s in SCENARIOS if s["id"] == scenario_id), None)
    npc_pool      = scenario_data.get("npc_pool", {}) if scenario_data else {}

    full_system = (SYSTEM_PROMPT
                   + build_scenario_context(req.state)
                   + build_opening_npc_context(req.state, npc_pool)
                   + OPENING_INSTRUCTION)
    content = await call_gemini([
        {"role": "system", "content": full_system},
        {"role": "user",   "content": "[게임 시작] 오프닝 장면을 생성하라."},
    ])
    content, extra = extract_state_update(content)
    return {
        "content":       content,
        "timestamp":     extract_timestamp(content),
        "state_updates": {"new_characters": extra.get("new_characters", [])},
    }


@router.post("/api/turn")
async def process_turn(req: TurnRequest):
    combat_state_in  = req.state.get("combatState")
    quality_mod      = None
    new_combat_state = None

    if combat_state_in and combat_state_in.get("active"):
        # ── 전투 진행 중 ──────────────────────────────────────────────────────
        if req.retreat:
            resolution, new_combat_state = resolve_retreat(req.state)
            sys_prompt_tail = combat_end_prompt(new_combat_state, resolution)
        else:
            resolution, new_combat_state = advance_combat_phase(req.command, req.state)
            if new_combat_state.get("ended"):
                sys_prompt_tail = combat_end_prompt(new_combat_state, resolution)
            else:
                completed_phase = new_combat_state.get("phase_number", 2) - 1
                sys_prompt_tail = combat_ongoing_prompt(completed_phase, combat_state_in, resolution)
    else:
        # ── 일반 턴 ───────────────────────────────────────────────────────────
        # 키워드 분류 (quality evaluator 힌트용 + needs_resolution 판단)
        kw_type = classify_action_type(req.command)

        # LLM 분류 + quality 평가 병렬 실행
        cls, quality_mod = await asyncio.gather(
            classify_action_llm(req.command, req.state),
            evaluate_action_quality(req.command, req.state, kw_type)
            if needs_resolution(req.command) else _async_none(),
        )

        cls_type      = cls.get("type", "general")
        resolver_type = CLS_TO_RESOLVER.get(cls_type, "general")

        if cls_type in ("open_field", "ambush", "siege_attack"):
            resolution, new_combat_state = init_combat_phase(
                req.command, req.state, quality_mod, classification=cls
            )
            sys_prompt_tail = combat_prep_prompt(new_combat_state, resolution)
        else:
            resolution      = resolve_action(
                req.command, req.state,
                quality_modifier=quality_mod, action_type=resolver_type,
            )
            sys_prompt_tail = resolution_prompt(resolution)

    full_system = SYSTEM_PROMPT + build_scenario_context(req.state) + sys_prompt_tail

    messages  = [{"role": "system", "content": full_system}]
    messages += [{"role": m.role, "content": m.content} for m in req.history]
    messages.append({"role": "user", "content": req.command})

    content = await call_gemini(messages)
    content, extra = extract_state_update(content)
    state_updates  = turn_engine(content, req.state)

    in_combat = bool(combat_state_in and combat_state_in.get("active"))
    for key in ("new_characters", "dead_characters", "new_factions", "defeated_factions",
                "faction_strength_changes", "faction_battle_recovery",
                "faction_diplomacy_changes", "faction_disposition_changes",
                "character_troop_changes", "character_disposition_changes", "character_title_changes",
                "faction_intel_changes", "new_locations", "location_changes"):
        if extra.get(key):
            state_updates[key] = extra[key]

    # 전투 페이즈 밖에서만 LLM의 faction_battle_damage를 수용
    if not in_combat and extra.get("faction_battle_damage"):
        state_updates["faction_battle_damage"] = extra["faction_battle_damage"]

    if isinstance(extra.get("weather"), str):
        state_updates["weather"] = extra["weather"]

    if new_combat_state is not None:
        for key in ("player_coalition", "enemy_coalition"):
            if isinstance(extra.get(key), list):
                new_combat_state[key] = extra[key]

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

        # phase_outcome: 전투 종결 시 즉시 피해 적용, 진행 중이면 다음 턴으로 이연
        if not new_combat_state.get("retreat"):
            phase_outcome = extra.get("phase_outcome")
            if phase_outcome:
                if new_combat_state.get("ended"):
                    p_label, e_label = combat_damage_labels(phase_outcome)
                    p_str = new_combat_state.get("player_strength", 100)
                    e_str = new_combat_state.get("enemy_strength",  100)
                    p_fid = new_combat_state.get("player_faction_id")
                    e_fid = new_combat_state.get("enemy_faction_id")
                    pending = dict(new_combat_state.get("pending_battle_damage", {}))
                    if p_fid: pending[p_fid] = pending.get(p_fid, 0) + calc_phase_damage(p_label, p_str)
                    if e_fid: pending[e_fid] = pending.get(e_fid, 0) + calc_phase_damage(e_label, e_str)
                    new_combat_state["pending_battle_damage"] = pending
                else:
                    new_combat_state["pending_phase_outcome"] = phase_outcome

        state_updates["combat_state"] = new_combat_state
        if new_combat_state.get("ended"):
            pending = new_combat_state.get("pending_battle_damage", {})
            state_updates["faction_battle_damage"] = [
                {"id": fid, "damage": dmg} for fid, dmg in pending.items() if dmg > 0
            ]

    return {
        "content":      content,
        "state_updates": state_updates,
        "resolution":   resolution,
        "_debug": {
            "state_update": extra,
            "quality_mod":  quality_mod,
        },
    }
