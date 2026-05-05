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
    "fortress": (+12, -8, "요새"),
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


def _terrain_modifier(command: str, state: dict, is_defense: bool) -> list[tuple[str, int]]:
    locations = state.get("locations", {})
    for loc in locations.values():
        name  = loc.get("name", "")
        short = name.split("(")[0].strip()
        if short and len(short) >= 2 and short in command:
            mods: list[tuple[str, int]] = []
            terrain_type        = _classify_terrain(loc.get("terrain", ""))
            def_v, atk_v, label = _TERRAIN_TABLE.get(terrain_type, (0, 0, ""))
            terrain_v = def_v if is_defense else atk_v
            if terrain_v and label:
                mods.append((f"{label} {'방어' if is_defense else '공략'}", terrain_v))
            garrison = loc.get("garrison", 0)
            if garrison:
                g_v = min(20, garrison // 500 * 2)
                if g_v:
                    mods.append(("수비대 지원" if is_defense else "수비대 저항",
                                 g_v if is_defense else -g_v))
            return mods
    return []


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
    modifiers.extend(_terrain_modifier(command, state, is_defense))

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


# ─────────────────────────────────────────────────────────────────────────────
# 다중 턴 전투 시스템
# ─────────────────────────────────────────────────────────────────────────────

# 준비 단계 결과 → 초기 사기 보정 (+: 유리, -: 불리)
_PREP_THRESHOLD_MOD: dict[str, int] = {
    "critical_success": +20,
    "success":          +10,
    "partial":            0,
    "failure":          -10,
    "critical_failure": -20,
}

# (적 사기 감소, 아군 사기 감소) per phase
# 실패하면 플레이어 사기가 깎이고, 부분 성공이면 양쪽 감소, 성공/대성공이면 적 사기만 깎임
_MORALE_DRAIN: dict[str, tuple[int, int]] = {
    "critical_success": (25,  0),
    "success":          (15,  0),
    "partial":          ( 8,  8),
    "failure":          ( 0, 15),
    "critical_failure": ( 0, 22),
}

# (적군 전투 피해, 아군 전투 피해) per phase — 전투 종료 시 faction.battle_damage에 일괄 적용
_PHASE_DAMAGE: dict[str, tuple[int, int]] = {
    "critical_success": (15,  0),
    "success":          (10,  3),
    "partial":          ( 5,  5),
    "failure":          ( 3, 10),
    "critical_failure": ( 0, 15),
}

_RETREAT_KW = {"후퇴", "퇴각", "철수", "물러", "돌아", "회군", "도망"}


def is_retreat(command: str) -> bool:
    return any(kw in command for kw in _RETREAT_KW)


def _calc_max_phases(total_strength: int) -> int:
    return max(2, min(20, total_strength // 50))


def _get_player_faction_id(state: dict) -> str | None:
    protagonist = state.get("protagonist")
    if not protagonist:
        return None
    chars      = state.get("characters", {})
    char       = chars.get(protagonist, {})
    faction_id = char.get("faction_id") or protagonist
    return faction_id if faction_id in state.get("factions", {}) else None


def _find_enemy_faction(command: str, state: dict) -> str | None:
    factions = state.get("factions", {})
    for fid, f in factions.items():
        name = f.get("name", "")
        if name and len(name) >= 2 and name in command:
            if f.get("disposition") in ("적대", "비우호"):
                return fid
    for disp in ("적대", "비우호"):
        for fid, f in factions.items():
            if f.get("disposition") == disp and not f.get("defeated"):
                return fid
    return None


def _get_faction_strength(faction_id: str, state: dict) -> int:
    f = state.get("factions", {}).get(faction_id, {})
    return max(0, (f.get("strength_score") or 0) - (f.get("battle_damage") or 0))


def _calc_threshold(own_str: int, opp_str: int, battle_damage: int, prep_mod: int) -> int:
    thr = 100 + prep_mod - battle_damage // 5
    if opp_str >= own_str * 2:
        thr -= 20
    elif opp_str >= own_str * 1.5:
        thr -= 10
    return max(40, thr)


def _final_from_morale(player_mom: int, enemy_mom: int) -> tuple[str, str]:
    """max_phases 소진 후 양측 잔여 사기로 최종 결과를 결정합니다."""
    if player_mom > enemy_mom * 1.5: return "성공",      "success"
    if player_mom > enemy_mom:       return "부분 성공", "partial"
    if enemy_mom  > player_mom * 1.5:return "실패",      "failure"
    if enemy_mom  > player_mom:      return "실패",      "failure"
    return                                  "부분 성공", "partial"  # 동수 → 비기기


def init_combat_phase(command: str, state: dict,
                      quality_modifier=None) -> tuple[dict, dict]:
    """전투 개시: 준비 단계 판정 + combat_state 초기화."""
    action_type = classify_action_type(command)
    resolution  = _resolve_military_action(command, state, action_type, quality_modifier)

    player_fid = _get_player_faction_id(state)
    enemy_fid  = _find_enemy_faction(command, state)

    player_str = _get_faction_strength(player_fid, state) if player_fid else 100
    enemy_str  = _get_faction_strength(enemy_fid,  state) if enemy_fid  else 100

    max_phases = _calc_max_phases(player_str + enemy_str)
    prep_mod   = _PREP_THRESHOLD_MOD.get(resolution["tier_en"], 0)

    p_dmg = state.get("factions", {}).get(player_fid or "", {}).get("battle_damage", 0)
    e_dmg = state.get("factions", {}).get(enemy_fid  or "", {}).get("battle_damage", 0)

    # 초기 사기 = 붕괴 임계값. 0이 되면 해당 진영 붕괴.
    player_morale = _calc_threshold(player_str, enemy_str, p_dmg,  prep_mod)
    enemy_morale  = _calc_threshold(enemy_str,  player_str, e_dmg, -prep_mod)

    pending: dict[str, int] = {}
    if player_fid: pending[player_fid] = 0
    if enemy_fid:  pending[enemy_fid]  = 0

    combat_state = {
        "active":                True,
        "phase_number":          1,
        "max_phases":            max_phases,
        "player_faction_id":     player_fid,
        "enemy_faction_id":      enemy_fid,
        "player_morale":       player_morale,
        "player_morale_max":   player_morale,
        "enemy_morale":        enemy_morale,
        "enemy_morale_max":    enemy_morale,
        "prep_tier_en":          resolution["tier_en"],
        "pending_battle_damage": pending,
        "phase_results":         [],
    }
    return resolution, combat_state


def advance_combat_phase(command: str, state: dict,
                         quality_modifier=None) -> tuple[dict, dict]:
    """전투 페이즈 한 턴 처리: 양측 사기 소진 + 누적 피해 갱신."""
    cs          = state.get("combatState", {})
    action_type = classify_action_type(command)
    if action_type not in ("military", "surprise", "defense"):
        action_type = "military"
    resolution  = _resolve_military_action(command, state, action_type, quality_modifier)

    tier_en      = resolution["tier_en"]
    e_drain, p_drain = _MORALE_DRAIN.get(tier_en, (10, 10))

    player_morale = max(0, cs.get("player_morale", 100) - p_drain)
    enemy_morale  = max(0, cs.get("enemy_morale",  100) - e_drain)
    phase_number    = cs.get("phase_number", 1)

    pending    = dict(cs.get("pending_battle_damage", {}))
    player_fid = cs.get("player_faction_id")
    enemy_fid  = cs.get("enemy_faction_id")
    e_dmg, p_dmg = _PHASE_DAMAGE.get(tier_en, (5, 5))
    if enemy_fid:  pending[enemy_fid]  = pending.get(enemy_fid,  0) + e_dmg
    if player_fid: pending[player_fid] = pending.get(player_fid, 0) + p_dmg

    phase_results = list(cs.get("phase_results", []))
    phase_results.append({"phase": phase_number, "tier_en": tier_en,
                          "player_morale": player_morale,
                          "enemy_morale":  enemy_morale})

    max_phases = cs.get("max_phases", 5)
    ended = (player_morale <= 0 or enemy_morale <= 0 or phase_number >= max_phases)

    new_cs: dict = {
        **cs,
        "player_morale":       player_morale,
        "enemy_morale":        enemy_morale,
        "phase_number":          phase_number + 1,
        "pending_battle_damage": pending,
        "phase_results":         phase_results,
        "active":                not ended,
    }
    if ended:
        if   player_morale <= 0 and enemy_morale > 0: ft, fte = "대실패",    "critical_failure"
        elif enemy_morale  <= 0 and player_morale > 0:ft, fte = "대성공",    "critical_success"
        else:                                              ft, fte = _final_from_morale(player_morale, enemy_morale)
        winner = "player" if fte in ("critical_success", "success", "partial") else "enemy"
        if fte == "partial":
            winner = "player" if player_morale >= enemy_morale else "enemy"
        new_cs.update({"ended": True, "winner": winner,
                       "final_tier": ft, "final_tier_en": fte})

    return resolution, new_cs


def resolve_retreat(state: dict) -> tuple[dict, dict]:
    """후퇴: 전투 즉시 종결, 아군 추가 전투 피해 20 부과."""
    cs         = state.get("combatState", {})
    player_fid = cs.get("player_faction_id")

    pending = dict(cs.get("pending_battle_damage", {}))
    if player_fid:
        pending[player_fid] = pending.get(player_fid, 0) + 20

    new_cs = {
        **cs,
        "active":                False,
        "ended":                 True,
        "winner":                "enemy",
        "retreat":               True,
        "final_tier":            "실패",
        "final_tier_en":         "failure",
        "pending_battle_damage": pending,
    }
    resolution = {"tier": "실패", "tier_en": "failure",
                  "roll": None, "net": None,
                  "action_type": "military", "modifiers": [("후퇴", 0)]}
    return resolution, new_cs


def combat_prep_prompt(cs: dict, resolution: dict) -> str:
    tier     = resolution.get("tier", "?")
    max_ph   = cs.get("max_phases", 5)
    p_mom    = cs.get("player_morale", 100)
    e_mom    = cs.get("enemy_morale",  100)
    return (
        "\n\n---\n"
        "## 전투 개시 — 준비 단계 판정 결과 (엔진 결정 — 반드시 준수)\n"
        f"전투 준비 결과: **{tier}**\n"
        f"예상 교전 단계: 최대 {max_ph}페이즈\n"
        f"아군 사기: {p_mom} | 적군 사기: {e_mom} (0이 되면 붕괴)\n\n"
        "이 결과에 따라 전투 개시 장면을 서술하시오.\n"
        "전투는 아직 진행 중이며 결과가 확정되지 않았다.\n"
        "장면 말미에 플레이어가 취할 수 있는 **전술적 선택지 3~4가지**를 제시하시오.\n"
        "(예: 정면 돌격, 측면 우회, 방어 진형 유지, 후퇴 — 구체적 전술 행동)"
    )


def combat_ongoing_prompt(resolved_phase: int, cs: dict, resolution: dict) -> str:
    tier      = resolution.get("tier", "?")
    p_mom     = cs.get("player_morale", 100)
    e_mom     = cs.get("enemy_morale",  100)
    remaining = max(0, cs.get("max_phases", 5) - cs.get("phase_number", 1) + 1)
    return (
        "\n\n---\n"
        f"## 전투 진행 — 페이즈 {resolved_phase} 판정 결과 (엔진 결정 — 반드시 준수)\n"
        f"이번 교전: **{tier}**\n"
        f"아군 사기: {p_mom} / 적군 사기: {e_mom} (0이 되면 붕괴)\n"
        f"잔여 페이즈: 최대 {remaining}턴\n\n"
        "이 판정에 따라 이번 교전 장면을 서술하시오.\n"
        "전투는 아직 끝나지 않았다. 다음 전술적 선택지를 제시하시오."
    )


def combat_end_prompt(cs: dict, resolution: dict) -> str:
    winner     = cs.get("winner", "?")
    retreat    = cs.get("retreat", False)
    final_tier = cs.get("final_tier", resolution.get("tier", "?"))
    p_mom      = cs.get("player_morale", 0)
    e_mom      = cs.get("enemy_morale",  0)
    pending    = cs.get("pending_battle_damage", {})

    if retreat:
        outcome = "플레이어 측이 **후퇴**하며 전투 종결"
    elif winner == "player":
        outcome = f"플레이어 측 **승리** — 최종 결과: {final_tier}"
    else:
        outcome = f"적 측 **승리** — 최종 결과: {final_tier}"

    dmg_lines = [f"  - {fid}: 피해 {dmg}" for fid, dmg in pending.items() if dmg > 0]
    dmg_str   = "\n".join(dmg_lines) if dmg_lines else "  없음"

    return (
        "\n\n---\n"
        "## 전투 종결 (엔진 결정 — 반드시 준수)\n"
        f"{outcome}\n"
        f"최종 사기 — 아군: {p_mom} / 적군: {e_mom}\n"
        f"누적 피해 처리:\n{dmg_str}\n\n"
        "전투 결과에 따라 전장 종결 장면을 서술하시오.\n"
        "승패와 그 여파, 양측의 상황 변화를 묘사하시오.\n"
        "전투 후 다음 행동 선택지를 제시하시오."
    )
