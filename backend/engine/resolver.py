"""
engine/resolver.py — 행동 판정 엔진

LLM 호출 전에 주사위 + 수정치로 결과 등급을 결정합니다.
결정된 등급은 시스템 프롬프트에 주입되어 LLM의 서술 방향을 고정합니다.

수정치 구성:
  군사 — 지형(고정) + LLM 품질 평가
  외교 — LLM 품질 평가만
  첩보 — LLM 품질 평가만
"""

import random

_MILITARY_KW   = {"공격","전투","포위","진격","돌격","출격","진군","침공","공세","교전","격파"}
_SURPRISE_KW   = {"기습","매복","야습","선제"}
_DEFENSE_KW    = {"방어","농성","수성","수비","진지","방비","지키","수호","막아","저지","저항","수비대"}
_DIPLOMATIC_KW = {"협상","외교","동맹","설득","교섭","협력","회담","제안","조건","강화","회유","타협","요청"}
_INTRIGUE_KW   = {"정찰","첩보","암살","침투","위장","간첩","밀서","내통","공작","염탐","잠입",
                  "모략","매수","이간","선동","유언비어","교란","와해","내응"}
_PASSIVE_KW    = {"관찰","기다","대기","확인","살펴","머문","쉬어","휴식","보고","상황"}

_ACTION_LABELS = {
    "military":   "전투",
    "surprise":   "기습",
    "defense":    "방어",
    "diplomatic": "외교",
    "intrigue":   "모략",
    "passive":    "서술",
    "general":    "일반",
}

# 지형 유형 → (방어 수정치, 공격 수정치, 레이블)
_TERRAIN_TABLE: dict[str, tuple[int, int, str]] = {
    "fortress": (+25, -15, "요새"),
    "highland": (+15,  -8, "고지"),
    "wetland":  (+12,  -8, "습지·하천"),
    "river":    ( +8,  -5, "강변 방어선"),
    "coastal":  (+10,  -5, "해안 요새"),
    "plain":    (  0,   0, "평원"),
}


def _classify_terrain(terrain_text: str) -> str:
    t = terrain_text
    if any(k in t for k in ["요새","성벽","성채","성곽","방벽","성"]): return "fortress"
    if any(k in t for k in ["협곡","절벽","산록","언덕","구릉","산"]): return "highland"
    if any(k in t for k in ["습지","늪","합류","합류부"]):              return "wetland"
    if any(k in t for k in ["강변","강안","강북","강남","강 합류"]):    return "river"
    if any(k in t for k in ["반도","해협","해안","해변"]):              return "coastal"
    return "plain"


def _terrain_modifier(command: str, state: dict, is_defense: bool) -> tuple[int, str | None]:
    locations = state.get("locations", {})
    for loc in locations.values():
        name  = loc.get("name", "")
        short = name.split("(")[0].strip()
        if short and len(short) >= 2 and short in command:
            terrain_type        = _classify_terrain(loc.get("terrain", ""))
            def_v, atk_v, label = _TERRAIN_TABLE.get(terrain_type, (0, 0, ""))
            if is_defense and def_v:
                return def_v, f"{label} 방어"
            if not is_defense and atk_v:
                return atk_v, f"{label} 공략"
    return 0, None


def classify_action_type(command: str) -> str:
    for kw in _SURPRISE_KW:
        if kw in command: return "surprise"
    for kw in _MILITARY_KW:
        if kw in command: return "military"
    for kw in _DEFENSE_KW:
        if kw in command: return "defense"
    for kw in _DIPLOMATIC_KW:
        if kw in command: return "diplomatic"
    for kw in _INTRIGUE_KW:
        if kw in command: return "intrigue"
    for kw in _PASSIVE_KW:
        if kw in command: return "passive"
    return "general"



def _narrative_resolution(action_type: str) -> dict:
    return {"tier": "서술", "tier_en": "narrate", "roll": None,
            "net": None, "action_type": action_type, "modifiers": []}


def _graded_resolution(action_type: str, roll: int, modifiers: list[tuple[str, int]]) -> dict:
    net = max(1, min(100, roll + sum(v for _, v in modifiers)))
    if   net >= 90: tier, tier_en = "대성공",    "critical_success"
    elif net >= 65: tier, tier_en = "성공",      "success"
    elif net >= 35: tier, tier_en = "부분 성공", "partial"
    elif net >= 15: tier, tier_en = "실패",      "failure"
    else:           tier, tier_en = "대실패",    "critical_failure"

    return {"tier": tier, "tier_en": tier_en, "roll": roll,
            "net": net, "action_type": action_type, "modifiers": modifiers}


def _resolve_military_action(command: str, state: dict, action_type: str,
                              quality_modifier: tuple[str, int] | None = None) -> dict:
    roll      = random.randint(1, 100)
    modifiers: list[tuple[str, int]] = []

    if quality_modifier:
        modifiers.append(quality_modifier)

    is_defense = action_type == "defense"
    terrain_v, terrain_label = _terrain_modifier(command, state, is_defense)
    if terrain_v and terrain_label:
        modifiers.append((terrain_label, terrain_v))

    return _graded_resolution(action_type, roll, modifiers)


def _resolve_diplomatic_action(quality_modifier: tuple[str, int] | None = None) -> dict:
    roll      = random.randint(1, 100)
    modifiers: list[tuple[str, int]] = []

    if quality_modifier:
        modifiers.append(quality_modifier)

    return _graded_resolution("diplomatic", roll, modifiers)


def _resolve_intrigue_action(quality_modifier: tuple[str, int] | None = None) -> dict:
    roll      = random.randint(1, 100)
    modifiers: list[tuple[str, int]] = []

    if quality_modifier:
        modifiers.append(quality_modifier)

    return _graded_resolution("intrigue", roll, modifiers)


def needs_resolution(command: str) -> bool:
    return classify_action_type(command) not in {"passive", "general"}


def resolve_action(command: str, state: dict,
                   quality_modifier: tuple[str, int] | None = None) -> dict:
    action_type = classify_action_type(command)
    if action_type in {"passive", "general"}:
        return _narrative_resolution(action_type)

    if action_type in {"military", "surprise", "defense"}:
        return _resolve_military_action(command, state, action_type, quality_modifier)
    if action_type == "diplomatic":
        return _resolve_diplomatic_action(quality_modifier)
    if action_type == "intrigue":
        return _resolve_intrigue_action(quality_modifier)
    return _narrative_resolution(action_type)


def resolution_prompt(res: dict) -> str:
    if res["tier_en"] == "narrate":
        return ""
    action_label = _ACTION_LABELS.get(res.get("action_type", ""), "행동")
    mod_str = ""
    if res["modifiers"]:
        parts   = [f"{lbl} {'+' if v > 0 else ''}{v}" for lbl, v in res["modifiers"]]
        mod_str = f" ({', '.join(parts)})"
    return (
        "\n\n---\n"
        "## 행동 판정 결과 (엔진 결정 — 반드시 준수)\n"
        f"판정 유형: **{action_label}**\n"
        f"결과: **{res['tier']}**\n"
        f"주사위: {res['roll']} → 보정 후 {res['net']}{mod_str}\n\n"
        "이 등급에 따라 서술하시오. 등급을 임의로 상향하지 마시오.\n"
        "- **대성공**: 기대 이상의 성과, 예상치 못한 이점 발생 가능\n"
        "- **성공**: 의도한 결과 달성, 큰 부작용 없음\n"
        "- **부분 성공**: 목표 일부 달성, 대가나 부작용 수반\n"
        "- **실패**: 목표 달성 못함, 상황이 다소 악화\n"
        "- **대실패**: 심각한 역효과, 예상치 못한 부정적 결과 발생\n"
        "세계관상 불가능한 행동은 이 판정과 무관하게 거부할 수 있음."
    )
