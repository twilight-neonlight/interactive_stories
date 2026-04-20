"""
engine/resolver.py — 행동 판정 엔진

LLM 호출 전에 주사위 + 게임 상태 수정치로 결과 등급을 결정합니다.
결정된 등급은 시스템 프롬프트에 주입되어 LLM의 서술 방향을 고정합니다.
"""

import random


def _eff_str(faction: dict, default: int = 350) -> float:
    """전투 피해를 반영한 실효 병력 강도를 반환합니다."""
    return faction.get("strength_score", default) - faction.get("battle_damage", 0)


_MILITARY_KW   = {"공격","전투","포위","진격","돌격","출격","진군","침공","공세","교전","격파"}
_SURPRISE_KW   = {"기습","매복","야습","선제"}
_DEFENSE_KW    = {"방어","농성","수성","수비","진지","방비","지키","수호","막아","저지","저항","수비대"}
_DIPLOMATIC_KW = {"협상","외교","동맹","설득","교섭","협력","회담","제안","조건","강화","회유","타협","요청"}
_STEALTH_KW    = {"정찰","첩보","암살","침투","위장","간첩","밀서","내통","공작","염탐","잠입"}
_PASSIVE_KW    = {"관찰","기다","대기","확인","살펴","머문","쉬어","휴식","보고","상황"}

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
    """명령어에 언급된 거점의 지형 수정치를 반환합니다."""
    locations = state.get("locations", {})
    for loc in locations.values():
        name  = loc.get("name", "")
        short = name.split("(")[0].strip()
        if short and len(short) >= 2 and short in command:
            terrain_type    = _classify_terrain(loc.get("terrain", ""))
            def_v, atk_v, label = _TERRAIN_TABLE.get(terrain_type, (0, 0, ""))
            if is_defense and def_v:
                return def_v, f"{label} 방어"
            if not is_defense and atk_v:
                return atk_v, f"{label} 공략"
    return 0, None


def _action_type(command: str) -> str:
    for kw in _SURPRISE_KW:
        if kw in command: return "surprise"
    for kw in _MILITARY_KW:
        if kw in command: return "military"
    for kw in _DEFENSE_KW:
        if kw in command: return "defense"
    for kw in _DIPLOMATIC_KW:
        if kw in command: return "diplomatic"
    for kw in _STEALTH_KW:
        if kw in command: return "stealth"
    for kw in _PASSIVE_KW:
        if kw in command: return "passive"
    return "general"


def resolve_action(command: str, state: dict) -> dict:
    """
    행동 유형을 분류하고 주사위 + 게임 상태 수정치로 결과 등급을 결정합니다.
    passive 행동(관찰/대기)은 판정을 생략합니다.
    """
    action_type = _action_type(command)

    if action_type == "passive":
        return {"tier": "서술", "tier_en": "narrate", "roll": None,
                "net": None, "action_type": action_type, "modifiers": []}

    roll = random.randint(1, 100)
    net  = roll
    modifiers: list[tuple[str, int]] = []

    factions       = state.get("factions", {})
    chars          = state.get("characters", {})
    protagonist_id = state.get("protagonist")

    player_char       = chars.get(protagonist_id, {}) if protagonist_id else {}
    player_faction_id = (player_char.get("faction_id") or player_char.get("faction")
                         or (protagonist_id if protagonist_id in factions else None))
    player_faction    = factions.get(player_faction_id, {}) if player_faction_id else {}

    enemy_factions = [f for f in factions.values() if f.get("disposition") == "적대"]
    ally_factions  = [f for f in factions.values()
                      if f.get("disposition") == "우호" and f.get("id") != player_faction_id]

    is_defense  = action_type == "defense"
    is_surprise = action_type == "surprise"

    # ── 군사·기습·방어·일반 수정치 ──────────────────────
    if action_type in ("military", "surprise", "defense", "general"):
        p_str = _eff_str(player_faction)
        if enemy_factions:
            e_str = sum(_eff_str(f) for f in enemy_factions) / len(enemy_factions)
            ratio = p_str / e_str if e_str > 0 else 9.0
            if   ratio >= 2.0:  v, label = +25, "병력 압도 (2배↑)"
            elif ratio >= 1.5:  v, label = +15, "병력 우세 (1.5배↑)"
            elif ratio >= 1.1:  v, label =  +5, "병력 우위"
            elif ratio >= 0.91: v, label =   0, None          # 중립 구간
            elif ratio >= 0.75: v, label = -10, "병력 열세 (0.75배↓)"
            elif ratio >= 0.5:  v, label = -20, "병력 대열세 (0.5배↓)"
            else:               v, label = -30, "병력 압도적 열세 (0.5배↓↓)"
            if label is not None: modifiers.append((label, v))
            net += v

        if ally_factions:
            a_str = sum(_eff_str(f) for f in ally_factions)
            if   a_str > 400: v, label = +15, "동맹 강력 지원"
            elif a_str > 200: v, label =  +8, "동맹 지원"
            else:             v = 0; label = None
            if v: modifiers.append((label, v)); net += v

        if is_surprise:
            modifiers.append(("기습 선공", +20)); net += 20

        terrain_v, terrain_label = _terrain_modifier(command, state, is_defense)
        if terrain_v and terrain_label:
            modifiers.append((terrain_label, terrain_v)); net += terrain_v

    # ── 외교 수정치 ──────────────────────────────────
    elif action_type == "diplomatic":
        dipl = player_faction.get("diplomacy_score", 0)
        if   dipl >  60: v, label = +20, "외교 기반 강함"
        elif dipl >  30: v, label = +10, "외교 기반 보통"
        elif dipl > -30: v, label =   0, None
        elif dipl > -60: v, label = -10, "외교 기반 약함"
        else:            v, label = -20, "외교 기반 매우 약함"
        if v: modifiers.append((label, v)); net += v

    # ── 첩보 수정치 ──────────────────────────────────
    elif action_type == "stealth":
        if enemy_factions:
            p_str = _eff_str(player_faction)
            e_str = sum(_eff_str(f) for f in enemy_factions) / len(enemy_factions)
            if   p_str > e_str + 100: v, label = +10, "우세한 정보망"
            elif p_str < e_str - 100: v, label = -10, "열세한 정보망"
            else:                     v = 0; label = None
            if v: modifiers.append((label, v)); net += v

    net = max(1, min(100, net))

    if   net >= 90: tier, tier_en = "대성공",    "critical_success"
    elif net >= 65: tier, tier_en = "성공",      "success"
    elif net >= 35: tier, tier_en = "부분 성공", "partial"
    elif net >= 15: tier, tier_en = "실패",      "failure"
    else:           tier, tier_en = "대실패",    "critical_failure"

    return {"tier": tier, "tier_en": tier_en, "roll": roll,
            "net": net, "action_type": action_type, "modifiers": modifiers}


def resolution_prompt(res: dict) -> str:
    """판정 결과를 시스템 프롬프트 주입용 텍스트로 변환합니다."""
    if res["tier_en"] == "narrate":
        return ""
    mod_str = ""
    if res["modifiers"]:
        parts   = [f"{lbl} {'+' if v > 0 else ''}{v}" for lbl, v in res["modifiers"]]
        mod_str = f" ({', '.join(parts)})"
    return (
        "\n\n---\n"
        "## 행동 판정 결과 (엔진 결정 — 반드시 준수)\n"
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
