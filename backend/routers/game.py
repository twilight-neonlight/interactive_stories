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
    calc_stat_modifier, _MIN_PHASES_BEFORE_VICTOR,
)
from engine.classifier import classify_action_llm, CLS_TO_RESOLVER
from engine.quality    import evaluate_action_quality
from engine.turn       import turn_engine, extract_state_update, extract_timestamp
from engine.context    import build_scenario_context, build_opening_context, OPENING_INSTRUCTION


_ACTION_STAT_KEY: dict[str, str] = {
    'military':   '통솔',
    'defense':    '통솔',
    'surprise':   '지략',
    'diplomatic': '외교',
    'intrigue':   '지략',
}


def _build_modifiers(*mods) -> list[tuple[str, int]] | None:
    """None 제거 후 수정치 리스트 반환. 빈 경우 None."""
    result = [m for m in mods if m is not None]
    return result if result else None


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

    scenario_prompts = _get_scenario_prompts(req.state)
    full_system = SYSTEM_PROMPT + build_scenario_context(req.state, scenario_prompts=scenario_prompts) + sys_prompt_tail

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

    return {
        "content":      content,
        "state_updates": state_updates,
        "resolution":   resolution,
        "_debug": {
            "state_update": extra,
            "quality_mod":  quality_mod,
        },
    }
