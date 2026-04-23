"""
routers/game.py — 오프닝·턴 처리 API
"""

from fastapi import APIRouter
from pydantic import BaseModel

from config          import SYSTEM_PROMPT
from gemini_client   import call_gemini
from scenarios_loader import SCENARIOS
from engine.resolver import resolve_action, resolution_prompt, needs_resolution, classify_action_type
from engine.quality  import evaluate_action_quality
from engine.turn     import turn_engine, extract_state_update, extract_timestamp
from engine.context  import build_scenario_context, build_opening_npc_context, OPENING_INSTRUCTION

router = APIRouter()


class Message(BaseModel):
    role: str
    content: str


class TurnRequest(BaseModel):
    command: str
    state:   dict
    history: list[Message]


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
    quality_mod = None
    action_type = classify_action_type(req.command)
    if needs_resolution(req.command):
        quality_mod = await evaluate_action_quality(req.command, req.state, action_type)

    resolution  = resolve_action(req.command, req.state, quality_modifier=quality_mod)
    full_system = SYSTEM_PROMPT + build_scenario_context(req.state) + resolution_prompt(resolution)

    messages = [{"role": "system", "content": full_system}]
    messages += [{"role": m.role, "content": m.content} for m in req.history]
    messages.append({"role": "user", "content": req.command})

    content = await call_gemini(messages)
    content, extra = extract_state_update(content)
    state_updates  = turn_engine(content, req.state)

    for key in ("new_characters", "dead_characters", "new_factions", "defeated_factions",
                "faction_strength_changes", "faction_battle_damage", "faction_battle_recovery",
                "faction_diplomacy_changes", "faction_disposition_changes",
                "character_troop_changes", "character_disposition_changes",
                "new_locations", "location_changes"):
        if extra.get(key):
            state_updates[key] = extra[key]

    return {"content": content, "state_updates": state_updates, "resolution": resolution}
