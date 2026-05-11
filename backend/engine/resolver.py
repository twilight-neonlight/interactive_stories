"""
engine/resolver.py — 행동 판정 엔진

LLM 호출 전에 주사위 + 수정치로 결과 등급을 결정합니다.
결정된 등급은 시스템 프롬프트에 주입되어 LLM의 서술 방향을 조정합니다.

일반 행동 판정 수정치 구성:
  군사 — 지형(고정) + 날씨 + LLM 품질 평가(최대 ±2)
  외교 — LLM 품질 평가(최대 ±2)
  첩보 — LLM 품질 평가(최대 ±2)

전투 시스템 — 2d6 대결 방식:
  각 페이즈: 아군 2d6 vs 적군 2d6. 차이(−10~+10)에 지형·날씨·성벽(tier 기반)·품질 수정치를 더해
  7단계 phase_outcome을 엔진이 직접 결정한다 (LLM은 phase_outcome을 출력하지 않음).
  결정된 phase_outcome은 pending_phase_outcome으로 저장되고, 다음 턴 시작 시 사기와 피해에 적용된다.
  전투 종결은 LLM의 combat_victor 신호 또는 플레이어 후퇴로만 결정된다.
"""

import random

_MILITARY_KW   = {"공격","전투","포위","진격","돌격","출격","진군","침공","공세","교전","격파","요격","포격","습격","타격","공습","폭격","토벌"}
_SURPRISE_KW   = {"기습","매복","야습","선제","은밀","급습","암습"}
_DEFENSE_KW    = {"방어","농성","수성","수비","진지","방비","지키","수호","막아","저지","저항","수비대"}
_SIEGE_KW      = {"공성","포위","공략"}
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

# 날씨 유형 → (공격측 수정치, 방어측 수정치, 레이블)
# 방어측(is_defense=True) 기준: 양수=유리, 음수=불리
_WEATHER_TABLE: dict[str, tuple[int, int, str]] = {
    "clear":      ( 0,  0, ""),
    "rain":       (-1,  0, "강우"),
    "heavy_rain": (-2,  0, "폭우"),
    "snow":       (-2,  0, "강설"),
    "blizzard":   (-3, +1, "눈보라"),
    "heat":       (-1, -1, "폭염"),
    "fog":        (-3,  0, "짙은 안개"),
    "storm":      (-3,  0, "폭풍"),
}


def _weather_modifier(state: dict, is_defense: bool) -> list[tuple[str, int]]:
    weather = state.get("weather", "clear")
    if not weather or weather == "clear":
        return []
    atk_v, def_v, label = _WEATHER_TABLE.get(weather, (0, 0, ""))
    v = def_v if is_defense else atk_v
    if v and label:
        return [(label, v)]
    return []


# 지형 유형 → (방어 수정치, 공격 수정치, 레이블)
# 요새는 tier 기반 성벽 수정치로 처리하므로 지형 테이블에서 제외
_TERRAIN_TABLE: dict[str, tuple[int, int, str]] = {
    "highland": (+2, -2, "고지"),
    "wetland":  (+1, -1, "습지·하천"),
    "river":    (+2, -2, "강변 방어선"),
    "plain":    ( 0,  0, "평원"),
}

# 거점 tier → 성벽 수정치 (방어측 보너스 / 공격측 패널티)
_TIER_WALL_BONUS: dict[str, int] = {
    "town":          0,
    "small_city":    1,
    "regional_city": 2,
    "major_city":    3,
    "metropolis":    4,
}


def _classify_terrain(terrain_text: str) -> str:
    t = terrain_text
    if any(k in t for k in ["협곡","절벽","산록","언덕","구릉","산"]): return "highland"
    if any(k in t for k in ["습지","늪","합류","합류부"]):              return "wetland"
    if any(k in t for k in ["강변","강안","강북","강남","강 합류"]):    return "river"
    return "plain"


def _find_siege_target(command: str, state: dict) -> tuple[str | None, int]:
    """공성 대상 거점 탐지 (키워드 폴백용). 반환: (location_id, garrison) 또는 (None, 0)"""
    if not any(kw in command for kw in _SIEGE_KW):
        return None, 0
    locations = state.get("locations", {})
    for loc_id, loc in locations.items():
        name  = loc.get("name", "")
        short = name.split("(")[0].strip()
        if short and len(short) >= 2 and short in command:
            garrison = loc.get("garrison", 0)
            if garrison:
                return loc_id, garrison
    return None, 0


def _find_location_by_name(name: str | None, locations: dict) -> tuple[str | None, int]:
    """지명 문자열로 거점 탐색. 반환: (location_id, garrison) 또는 (None, 0)"""
    if not name:
        return None, 0
    for loc_id, loc in locations.items():
        short = loc.get("name", "").split("(")[0].strip()
        if short and (name in short or short in name):
            garrison = loc.get("garrison", 0)
            if garrison:
                return loc_id, garrison
    return None, 0


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
            wall_v = _TIER_WALL_BONUS.get(loc.get("tier", ""), 0)
            if wall_v:
                mods.append(("성벽" if is_defense else "성벽 저항",
                             wall_v if is_defense else -wall_v))
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
    net = max(4, min(28, roll + sum(v for _, v in modifiers)))
    if   net >= 21: tier, tier_en = "대성공",    "critical_success"
    elif net >= 17: tier, tier_en = "성공",      "success"
    elif net >= 12: tier, tier_en = "부분 성공", "partial"
    elif net >= 8:  tier, tier_en = "실패",      "failure"
    else:           tier, tier_en = "대실패",    "critical_failure"

    return {"tier": tier, "tier_en": tier_en, "roll": roll,
            "net": net, "action_type": action_type, "modifiers": modifiers}


def _resolve_military_action(action_type: str,
                              quality_modifier: tuple[str, int] | None = None) -> dict:
    roll      = sum(random.randint(1, 6) for _ in range(4))
    modifiers: list[tuple[str, int]] = []

    if quality_modifier:
        modifiers.append(quality_modifier)

    res = _graded_resolution(action_type, roll, modifiers)
    res["luck_label"] = res["tier"]
    res["luck_shift"] = res["net"] - roll
    return res


# ─────────────────────────────────────────────────────────────────────────────
# 전투 페이즈 주사위 — 1d12 + 지형 + 날씨 + 전술 품질 → phase_outcome
# ─────────────────────────────────────────────────────────────────────────────

_PHASE_OUTCOME_KO: dict[str, str] = {
    "critical_success": "결정적 우세",
    "major_success":    "전술 우세",
    "minor_success":    "소폭 우세",
    "stalemate":        "교착",
    "minor_fail":       "소폭 열세",
    "major_fail":       "전술 열세",
    "critical_fail":    "결정적 열세",
}


def _net_to_phase_outcome(net: int) -> str:
    # 기준: 아군2d6 - 적군2d6 대결 차이(-10~+10) + 수정치
    if net >= 9:  return "critical_success"
    if net >= 6:  return "major_success"
    if net >= 3:  return "minor_success"
    if net >= -2: return "stalemate"       # -2 ~ +2
    if net >= -5: return "minor_fail"      # -3 ~ -5
    if net >= -8: return "major_fail"      # -6 ~ -8
    return "critical_fail"                 # ≤ -9


def _resolve_phase_dice(command: str, state: dict, action_type: str,
                        quality_modifier: tuple[str, int] | None = None) -> dict:
    """전투 페이즈 주사위. (아군 2d6 − 적군 2d6) + 지형 + 날씨 + 전술 품질 → phase_outcome."""
    a = sum(random.randint(1, 6) for _ in range(2))  # 아군 2d6
    b = sum(random.randint(1, 6) for _ in range(2))  # 적군 2d6
    roll = a - b                                      # 대결 차이: -10 ~ +10
    modifiers: list[tuple[str, int]] = []

    is_defense = action_type == "defense"
    modifiers.extend(_terrain_modifier(command, state, is_defense))
    modifiers.extend(_weather_modifier(state, is_defense))
    if quality_modifier:
        modifiers.append(quality_modifier)

    net           = roll + sum(v for _, v in modifiers)
    phase_outcome = _net_to_phase_outcome(net)

    return {
        "tier":          _PHASE_OUTCOME_KO.get(phase_outcome, "?"),
        "tier_en":       "phase_dice",
        "roll":          roll,
        "roll_detail":   {"ally": a, "enemy": b},
        "net":           net,
        "phase_outcome": phase_outcome,
        "action_type":   action_type,
        "modifiers":     modifiers,
    }


def _resolve_diplomatic_action(quality_modifier: tuple[str, int] | None = None) -> dict:
    roll      = sum(random.randint(1, 6) for _ in range(4))
    modifiers: list[tuple[str, int]] = []

    if quality_modifier:
        modifiers.append(quality_modifier)

    return _graded_resolution("diplomatic", roll, modifiers)


def _resolve_intrigue_action(quality_modifier: tuple[str, int] | None = None) -> dict:
    roll      = sum(random.randint(1, 6) for _ in range(4))
    modifiers: list[tuple[str, int]] = []

    if quality_modifier:
        modifiers.append(quality_modifier)

    return _graded_resolution("intrigue", roll, modifiers)


def needs_resolution(command: str) -> bool:
    return classify_action_type(command) not in {"passive", "general"}


def resolve_action(command: str, state: dict,
                   quality_modifier: tuple[str, int] | None = None,
                   action_type: str | None = None) -> dict:
    if action_type is None:
        action_type = classify_action_type(command)
    if action_type in {"passive", "general"}:
        return _narrative_resolution(action_type)

    if action_type in {"military", "surprise", "defense"}:
        return _resolve_military_action(action_type, quality_modifier)
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
# 다중 페이즈 전투 시스템 — 적 행동 예고 방식
# ─────────────────────────────────────────────────────────────────────────────

# 사상자 규모 레이블 → (최소, 최대) 절댓값 battle_damage 포인트 (0–700 스케일 기준)
# 비율이 아닌 고정 범위 — 전력 크기와 무관하게 1페이즈당 손실을 예측 가능하게 유지
DAMAGE_LABEL_RATIO: dict[str, tuple[int, int]] = {
    "경미": (1,  3),
    "보통": (3,  7),
    "중대": (7, 14),
    "심각": (14, 25),
    "궤멸": (25, 40),
}

# phase_outcome → (player_damage_label, enemy_damage_label)
_PHASE_OUTCOME_DAMAGE: dict[str, tuple[str, str]] = {
    "critical_success": ("경미", "궤멸"),
    "major_success":    ("보통", "심각"),
    "minor_success":    ("보통", "중대"),
    "stalemate":        ("경미", "경미"),
    "minor_fail":       ("중대", "보통"),
    "major_fail":       ("심각", "보통"),
    "critical_fail":    ("궤멸", "경미"),
}


def _apply_phase_morale(outcome: str,
                        player_morale: int, enemy_morale: int) -> tuple[int, int]:
    """페이즈 결과에 따라 양측 사기를 조정합니다."""
    if outcome == "critical_success":
        player_morale += random.randint(5, 10)
        enemy_morale  -= random.randint(35, 70)
    elif outcome == "major_success":
        player_morale += random.randint(3, 5)
        enemy_morale  -= random.randint(15, 35)
    elif outcome == "minor_success":
        enemy_morale  -= random.randint(7, 15)
    elif outcome == "stalemate":
        player_morale -= random.randint(3, 7)
        enemy_morale  -= random.randint(3, 7)
    elif outcome == "minor_fail":
        player_morale -= random.randint(7, 15)
    elif outcome == "major_fail":
        enemy_morale  += random.randint(3, 5)
        player_morale -= random.randint(15, 35)
    elif outcome == "critical_fail":
        enemy_morale  += random.randint(5, 10)
        player_morale -= random.randint(35, 70)
    return max(0, min(100, player_morale)), max(0, min(100, enemy_morale))




def combat_damage_labels(phase_outcome: str) -> tuple[str, str]:
    """phase_outcome을 (player_label, enemy_label)로 변환합니다."""
    return _PHASE_OUTCOME_DAMAGE.get(phase_outcome, ("경미", "경미"))


# 최대 페이즈 수 (안전 한계 — 초과 시 누적 피해 기준으로 승패 결정)
_MAX_PHASES = 25

# 이 페이즈 수 이상 교전해야 combat_victor 신호를 수용
_MIN_PHASES_BEFORE_VICTOR = 3


def calc_phase_damage(label: str, ratio: float = 1.0) -> int:
    """레이블 × 병력비(소수점 1자리)로 battle_damage 포인트를 반환합니다."""
    lo, hi = DAMAGE_LABEL_RATIO.get(label, DAMAGE_LABEL_RATIO["경미"])
    if hi == 0:
        return 0
    return max(0, round(random.randint(lo, hi) * round(ratio, 1)))


def _get_player_faction_id(state: dict) -> str | None:
    protagonist = state.get("protagonist")
    if not protagonist:
        return None
    chars      = state.get("characters", {})
    char       = chars.get(protagonist, {})
    faction_id = char.get("faction_id") or protagonist
    return faction_id if faction_id in state.get("factions", {}) else None


def _is_hostile(f: dict) -> bool:
    """disposition 필드 또는 diplomacy_score로 적대 여부를 판단합니다."""
    if f.get("defeated"):
        return False
    if f.get("disposition") in ("적대", "비우호"):
        return True
    score = f.get("diplomacy_score")
    return score is not None and score < -33


def _find_enemy_faction(command: str, state: dict) -> str | None:
    factions = state.get("factions", {})

    # 1. 전체 이름 매치 + 적대 세력
    for fid, f in factions.items():
        name = f.get("name", "")
        if name and len(name) >= 2 and name in command and _is_hostile(f):
            return fid

    # 2. 부분 이름 매치 (공백 분리 2자 이상 단어) + 적대 세력
    for fid, f in factions.items():
        if not _is_hostile(f):
            continue
        words = [w for w in f.get("name", "").split() if len(w) >= 2]
        if any(w in command for w in words):
            return fid

    # 3. 폴백: disposition 기준 첫 적대 → 비우호 세력
    for disp in ("적대", "비우호"):
        for fid, f in factions.items():
            if f.get("disposition") == disp and not f.get("defeated"):
                return fid

    # 4. 폴백: diplomacy_score 기준 첫 적대 세력
    for fid, f in factions.items():
        if _is_hostile(f):
            return fid

    return None


def _get_faction_strength(faction_id: str, state: dict) -> int:
    f = state.get("factions", {}).get(faction_id, {})
    return max(0, (f.get("strength_score") or 0) - (f.get("battle_damage") or 0))


_SIEGE_TERRAIN_MULT: dict[str, float] = {
    "fortress": 1.6,
    "highland": 1.4,
    "river":    1.3,
    "wetland":  1.2,
    "plain":    1.1,
}


def init_combat_phase(command: str, state: dict,
                      quality_modifier=None,
                      classification: dict | None = None) -> tuple[dict, dict]:
    """전투 개시: 준비 단계 판정 + combat_state 초기화.

    classification: classifier.classify_action_llm 결과 dict.
      type == "siege_attack" → 공성전, location_name으로 거점 탐색.
      type == "open_field"/"ambush" → 야전 강제 (공성 탐지 건너뜀).
      None → 키워드 기반 폴백으로 판단.
    """
    action_type = classify_action_type(command)
    if action_type not in ("military", "surprise", "defense"):
        action_type = "military"

    player_fid = _get_player_faction_id(state)
    player_str = _get_faction_strength(player_fid, state) if player_fid else 100

    locations  = state.get("locations", {})
    cls_type   = classification.get("type")   if classification else None
    cls_loc    = classification.get("location_name") if classification else None

    # 공성전 여부 결정
    if cls_type == "siege_attack":
        # LLM이 공성으로 분류 → 지명으로 거점 탐색
        siege_loc_id, garrison = _find_location_by_name(cls_loc, locations)
        if not garrison:
            # 지명 탐색 실패 → 키워드 폴백
            siege_loc_id, garrison = _find_siege_target(command, state)
        is_siege = garrison > 0
    elif cls_type in ("open_field", "ambush") or (classification is not None and cls_type != "siege_attack"):
        # LLM이 야전으로 분류 → 공성 탐지 건너뜀
        is_siege, siege_loc_id, garrison = False, None, 0
    else:
        # 폴백: 키워드 기반
        siege_loc_id, garrison = _find_siege_target(command, state)
        is_siege = garrison > 0

    locations = state.get("locations", {})
    if is_siege:
        loc        = locations.get(siege_loc_id, {})
        controller = loc.get("controller")
        factions   = state.get("factions", {})
        enemy_fid  = controller if controller in factions else _find_enemy_faction(command, state)
        tpp        = state.get("troopsPerPoint", 65)
        base_str   = max(10, round(garrison / tpp))
        terrain_type = _classify_terrain(loc.get("terrain", ""))
        mult       = _SIEGE_TERRAIN_MULT.get(terrain_type, 1.1)
        enemy_str  = max(10, round(base_str * mult))
        loc_name   = loc.get("name", "").split("(")[0].strip() or cls_loc
    else:
        siege_loc_id = None
        garrison     = 0
        enemy_fid  = _find_enemy_faction(command, state)
        enemy_str  = _get_faction_strength(enemy_fid, state) if enemy_fid else 100
        # 지명: LLM 제공 우선 → locations 키워드 탐색 순서
        if cls_loc:
            loc_name = cls_loc
        else:
            loc_name = None
            for loc in locations.values():
                name  = loc.get("name", "")
                short = name.split("(")[0].strip()
                if short and len(short) >= 2 and short in command:
                    loc_name = short
                    break

    pending: dict[str, int] = {}
    if player_fid: pending[player_fid] = 0
    if enemy_fid:  pending[enemy_fid]  = 0

    # 개시 페이즈 주사위 (적 예고 행동 없으므로 quality modifier 없이 지형·날씨만 반영)
    resolution = _resolve_phase_dice(command, state, action_type)

    combat_state = {
        "active":                True,
        "phase_number":          1,
        "player_faction_id":     player_fid,
        "enemy_faction_id":      enemy_fid,
        "player_strength":       player_str,
        "enemy_strength":        enemy_str,
        "player_morale":         100,
        "enemy_morale":          100,
        "enemy_next_action":     None,
        "pending_phase_outcome": resolution["phase_outcome"],
        "pending_battle_damage": pending,
        "phase_results":         [],
        "is_siege":              is_siege,
        "siege_location_id":     siege_loc_id,
        "siege_garrison":        garrison,
        "battle_location_name":  loc_name,
    }
    return resolution, combat_state


def advance_combat_phase(command: str, state: dict,
                         quality_modifier=None) -> tuple[dict, dict]:
    """전투 페이즈 한 턴: 이전 phase_outcome 피해 적용 → 이번 주사위 사기 즉시 반영 → 사기 붕괴 확인."""
    cs          = state.get("combatState", {})
    action_type = classify_action_type(command)
    if action_type not in ("military", "surprise", "defense"):
        action_type = "military"

    resolution = _resolve_phase_dice(command, state, action_type, quality_modifier)

    phase_number    = cs.get("phase_number", 1)
    player_morale   = cs.get("player_morale", 100)
    enemy_morale    = cs.get("enemy_morale", 100)
    pending         = dict(cs.get("pending_battle_damage", {}))
    pending_outcome = cs.get("pending_phase_outcome")
    p_fid = cs.get("player_faction_id")
    e_fid = cs.get("enemy_faction_id")
    p_str = cs.get("player_strength", 100)
    e_str = cs.get("enemy_strength",  100)

    # 이전 턴 phase_outcome → 피해 누적 (deferred)
    if pending_outcome:
        p_label, e_label = combat_damage_labels(pending_outcome)
        p_ratio = e_str / max(1, p_str)
        e_ratio = p_str / max(1, e_str)
        if p_fid: pending[p_fid] = pending.get(p_fid, 0) + calc_phase_damage(p_label, p_ratio)
        if e_fid: pending[e_fid] = pending.get(e_fid, 0) + calc_phase_damage(e_label, e_ratio)

    # 이번 턴 phase_outcome → 사기 즉시 적용
    player_morale, enemy_morale = _apply_phase_morale(
        resolution["phase_outcome"], player_morale, enemy_morale
    )

    morale_collapse = player_morale <= 0 or enemy_morale <= 0
    if morale_collapse:
        collapsed_fid = (p_fid if player_morale <= 0 else e_fid)
        collapsed_str = (p_str if player_morale <= 0 else e_str)
        if collapsed_fid:
            rout_dmg = max(1, round(collapsed_str * random.uniform(0.08, 0.15)))
            pending[collapsed_fid] = pending.get(collapsed_fid, 0) + rout_dmg

    force_end = phase_number >= _MAX_PHASES or morale_collapse

    phase_results = list(cs.get("phase_results", []))
    phase_results.append({
        "phase":         phase_number,
        "phase_outcome": resolution["phase_outcome"],
        "tier":          resolution["tier"],
        "roll":          resolution["roll"],
        "roll_detail":   resolution.get("roll_detail", {}),
        "net":           resolution["net"],
        "modifiers":     resolution.get("modifiers", []),
        "player_action": command[:80],
        "enemy_action":  cs.get("enemy_next_action") or "",
    })

    new_cs: dict = {
        **cs,
        "phase_number":          phase_number + 1,
        "player_morale":         player_morale,
        "enemy_morale":          enemy_morale,
        "enemy_next_action":     None,
        "pending_phase_outcome": None,
        "pending_battle_damage": pending,
        "phase_results":         phase_results,
        "active":                not force_end,
    }

    if force_end:
        if player_morale <= 0:
            winner, ft, fte = "enemy", "실패", "failure"
        elif enemy_morale <= 0:
            winner, ft, fte = "player", "성공", "success"
        else:
            # 최대 페이즈 도달: 이번 주사위 결과 즉시 적용 후 누적 피해로 판정
            cur_outcome = resolution["phase_outcome"]
            p_ratio = e_str / max(1, p_str)
            e_ratio = p_str / max(1, e_str)
            p_label, e_label = combat_damage_labels(cur_outcome)
            if p_fid: pending[p_fid] = pending.get(p_fid, 0) + calc_phase_damage(p_label, p_ratio)
            if e_fid: pending[e_fid] = pending.get(e_fid, 0) + calc_phase_damage(e_label, e_ratio)
            new_cs["pending_battle_damage"] = pending
            p_dmg  = pending.get(p_fid, 0)
            e_dmg  = pending.get(e_fid, 0)
            winner = "player" if e_dmg >= p_dmg else "enemy"
            ft, fte = ("부분 성공", "partial") if winner == "player" else ("실패", "failure")
        new_cs.update({"ended": True, "winner": winner,
                       "final_tier": ft, "final_tier_en": fte})
    else:
        new_cs["pending_phase_outcome"] = resolution["phase_outcome"]

    return resolution, new_cs


def resolve_retreat(state: dict) -> tuple[dict, dict]:
    """후퇴: 전투 즉시 종결, 아군 전력 3~5% 추가 피해."""
    cs         = state.get("combatState", {})
    player_fid = cs.get("player_faction_id")
    player_str = cs.get("player_strength", 100)

    retreat_dmg = max(1, round(player_str * random.uniform(0.03, 0.05)))
    pending = dict(cs.get("pending_battle_damage", {}))
    if player_fid:
        pending[player_fid] = pending.get(player_fid, 0) + retreat_dmg

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
    roll_detail = resolution.get("roll_detail", {})
    ally_roll   = roll_detail.get("ally", "?")
    enemy_roll  = roll_detail.get("enemy", "?")
    net         = resolution.get("net", 0)
    tier        = resolution.get("tier", "?")
    modifiers   = resolution.get("modifiers", [])
    p_str       = cs.get("player_strength", 100)
    e_str       = cs.get("enemy_strength",  100)
    is_siege    = cs.get("is_siege", False)
    garrison    = cs.get("siege_garrison", 0)

    mod_str = ""
    if modifiers:
        parts   = [f"{lbl} {'+' if v > 0 else ''}{v}" for lbl, v in modifiers]
        mod_str = f" ({', '.join(parts)})"

    if is_siege:
        battle_header = "## 공성전 개시 — 전투 상태 설정 (엔진 결정 — 반드시 준수)\n"
        strength_line = (
            f"아군 전력: {p_str} | "
            f"수비대 {garrison:,}명 (방어 보너스 포함 실효 전력: {e_str}) — "
            "야전군 미포함, 수비대만 응전\n"
        )
        enemy_label = "수비대"
    else:
        battle_header = "## 전투 개시 — 전투 상태 설정 (엔진 결정 — 반드시 준수)\n"
        strength_line = f"아군 전력: {p_str} | 적군 전력: {e_str}\n"
        enemy_label = "적군"

    return (
        "\n\n---\n"
        + battle_header
        + strength_line + "\n"
        f"주사위: 아군 {ally_roll} vs 적군 {enemy_roll} → 차이 {net:+d}{mod_str} → **{tier}**\n\n"
        "**[절대 금지 — 위반 불가]** 플레이어가 후퇴 명령을 입력하기 전까지, "
        "상황이 불리하더라도 아군은 전투를 계속한다. "
        "서술 내에서 아군의 퇴각·철수·후퇴를 실행하거나 기정사실로 묘사하지 말 것. "
        "부하가 퇴각을 건의하는 대사는 허용되나, 퇴각 실행 여부는 반드시 플레이어의 다음 입력으로만 결정된다.\n"
        "**[절대 금지]** 전투 개시 직후이므로 적군의 사기 붕괴·패주·자멸 묘사는 금지한다. "
        "피해와 압박은 묘사할 수 있으나, 적이 먼저 무너지거나 도망가는 묘사는 할 수 없다.\n\n"
        "현재 공개 전황만을 바탕으로 전투 개시 장면을 서술하시오. 전투는 아직 진행 중이다.\n"
        "장면 말미에 플레이어가 취할 수 있는 **전술적 선택지 3가지**를 먼저 제시하시오.\n"
        "(구체적인 전술 행동 — 후퇴는 선택지에 포함하지 말 것)\n\n"
        "STATE_UPDATE 필수 출력:\n"
        f"- `enemy_next_action`: {enemy_label}이 다음 페이즈에 시도할 방어·전술 행동 — "
        "1~2문장. 전술적으로 개연성 있게 작성하시오. "
        "본문 선택지나 서술에 암시하지 말고 STATE_UPDATE에만 기록하시오.\n"
        "- `combat_victor`: 전투가 이미 사실상 결판났다면 \"player\" 또는 \"enemy\", "
        "그렇지 않으면 반드시 null\n"
    )


def combat_ongoing_prompt(resolved_phase: int, old_cs: dict, resolution: dict) -> str:
    roll_detail   = resolution.get("roll_detail", {})
    ally_roll     = roll_detail.get("ally", "?")
    enemy_roll    = roll_detail.get("enemy", "?")
    net           = resolution.get("net", 0)
    tier          = resolution.get("tier", "?")
    modifiers     = resolution.get("modifiers", [])
    enemy_action  = old_cs.get("enemy_next_action") or "(불명)"
    p_str         = old_cs.get("player_strength", 100)
    e_str         = old_cs.get("enemy_strength",  100)
    p_morale      = old_cs.get("player_morale", 100)
    e_morale      = old_cs.get("enemy_morale",  100)
    can_end       = resolved_phase >= _MIN_PHASES_BEFORE_VICTOR
    is_siege      = old_cs.get("is_siege", False)
    garrison      = old_cs.get("siege_garrison", 0)
    phase_results = old_cs.get("phase_results", [])
    had_critical  = (
        any(r.get("phase_outcome") == "critical_success" for r in phase_results)
        or resolution.get("phase_outcome") == "critical_success"
    )
    enemy_rout_forbidden = e_morale > 30 and not had_critical

    mod_str = ""
    if modifiers:
        parts   = [f"{lbl} {'+' if v > 0 else ''}{v}" for lbl, v in modifiers]
        mod_str = f" ({', '.join(parts)})"

    if is_siege:
        battle_header = f"## 공성전 진행 — 페이즈 {resolved_phase} (엔진 결정 — 반드시 준수)\n"
        strength_line = (
            f"아군 전력: {p_str} | 수비대 실효 전력: {e_str} (원 수비대 {garrison:,}명)\n"
            f"아군 사기: {p_morale} | 수비대 사기: {e_morale}\n"
        )
        enemy_label = "수비대"
    else:
        battle_header = f"## 전투 진행 — 페이즈 {resolved_phase} (엔진 결정 — 반드시 준수)\n"
        strength_line = (
            f"아군 전력: {p_str} | 적군 전력: {e_str}\n"
            f"아군 사기: {p_morale} | 적군 사기: {e_morale}\n"
        )
        enemy_label = "적군"

    return (
        "\n\n---\n"
        + battle_header
        + strength_line
        + f"주사위: 아군 {ally_roll} vs 적군 {enemy_roll} → 차이 {net:+d}{mod_str} → **{tier}**\n\n"
        "**이번 페이즈 행동 대결:**\n"
        f"- {enemy_label} 예고 행동: {enemy_action}\n"
        "- 플레이어 행동: (위 user 메시지 참조)\n\n"
        "주사위 결과(위)를 바탕으로 이번 페이즈가 어떻게 전개됐는지 서술하시오. "
        "두 행동이 전장에서 어떻게 맞물리는지 전술적으로 묘사하되, 판정 등급을 반드시 반영하시오. "
        "판정 등급을 임의로 상향하거나 하향하지 마시오.\n\n"
        "**[절대 금지 — 위반 불가]** 플레이어가 후퇴 명령을 입력하기 전까지, "
        "결과가 불리하더라도 아군은 전투를 계속한다. "
        "서술 내에서 아군의 퇴각·철수·후퇴를 실행하거나 기정사실로 묘사하지 말 것.\n"
        + (
            f"**[절대 금지]** 현재 적 사기({e_morale})가 30 초과이고 '결정적 우세' 판정이 아직 없었다. "
            "적군이 스스로 무너지거나 패주·궤멸하는 묘사는 금지한다. "
            "피해·후퇴 압박은 묘사할 수 있으나, 사기 붕괴·도주 실행은 서술하지 마시오.\n\n"
            if enemy_rout_forbidden else "\n"
        )
        + "장면 말미에 다음 전술적 선택지 3가지를 제시하시오. "
        "선택지는 반드시 **현재 진행 중인 전투 안에서 취할 수 있는 전술 행동**이어야 한다. "
        "후퇴·철수·전장 이탈·'군대를 돌린다'·전투 종료 후 행동은 절대 포함하지 말 것. "
        "`enemy_next_action`은 STATE_UPDATE에만 기록하고 본문에는 노출하지 마시오.\n\n"
        "STATE_UPDATE 필수 출력:\n"
        f"- `enemy_next_action`: {enemy_label}이 다음 페이즈에 시도할 방어·전술 행동 (1~2문장)\n"
        + (
            "- `combat_victor`: 전투가 사실상 종결됐다면 \"player\" 또는 \"enemy\", "
            "진행 중이면 null"
            if can_end else
            "- `combat_victor`: null — 아직 교전이 충분하지 않다"
        )
    )


def combat_end_prompt(cs: dict, resolution: dict) -> str:
    winner     = cs.get("winner", "?")
    retreat    = cs.get("retreat", False)
    final_tier = cs.get("final_tier", resolution.get("tier", "?"))
    pending    = cs.get("pending_battle_damage", {})
    is_siege   = cs.get("is_siege", False)
    siege_lid  = cs.get("siege_location_id")

    if retreat:
        outcome = "플레이어 측이 **후퇴**하며 전투 종결"
    elif winner == "player":
        if is_siege:
            outcome = f"**공성 성공** — 거점 점령 — 최종 결과: {final_tier}"
        else:
            outcome = f"플레이어 측 **승리** — 최종 결과: {final_tier}"
    else:
        if is_siege:
            outcome = f"**공성 실패** — 수비대 격퇴 — 최종 결과: {final_tier}"
        else:
            outcome = f"적 측 **승리** — 최종 결과: {final_tier}"

    dmg_lines = [f"  - {fid}: 피해 {dmg}" for fid, dmg in pending.items() if dmg > 0]
    dmg_str   = "\n".join(dmg_lines) if dmg_lines else "  없음"

    siege_note = ""
    if is_siege and winner == "player" and siege_lid:
        siege_note = (
            f"\n공성 성공 시 STATE_UPDATE `location_changes`에 거점 id `{siege_lid}`의 "
            "controller를 플레이어 세력 id로 반드시 업데이트하시오.\n"
        )

    return (
        "\n\n---\n"
        + ("## 공성전 종결 (엔진 결정 — 반드시 준수)\n" if is_siege
           else "## 전투 종결 (엔진 결정 — 반드시 준수)\n")
        + f"{outcome}\n"
        f"누적 피해 처리:\n{dmg_str}\n"
        + siege_note + "\n"
        "전투 결과에 따라 전장 종결 장면을 서술하시오.\n"
        "승패와 그 여파, 양측의 상황 변화를 묘사하시오.\n"
        "사상자 서술 시 총 손실의 약 1/4은 전사자, 3/4은 중상자·탈영자·낙오자로 구성된다. "
        "부상자 다수는 시간이 지나면 전열에 복귀할 수 있다.\n"
        "패배한 세력이 반군·잔당 계열(rebels/remnant 유형)이고 지배 거점이 없으며 잔존 전력이 "
        "impotent 수준(strength_score 100 미만)이라면, STATE_UPDATE의 defeated_factions에 해당 세력 id를 반드시 포함하시오.\n"
        "전투 후 다음 행동 선택지를 제시하시오."
    )
