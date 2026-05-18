"""
engine/context.py — LLM 시나리오 컨텍스트 빌더

현재 게임 상태를 시스템 프롬프트에 주입할 텍스트로 변환합니다.
오프닝 전용 NPC 컨텍스트 빌더도 포함합니다.
"""

import re


OPENING_INSTRUCTION = """

---
## 오프닝 장면 생성 지시 (게임 첫 턴 — 반드시 준수)

플레이어가 게임에 처음 진입했다. 일반 턴이 아닌 **오프닝 장면**을 작성하라.

### 형식
- `## 1장, SCENE 1` 헤더로 시작
- `**시각:**` 줄 포함 (시나리오 맥락에 맞는 시점·장소)

### 장면 구성
- 플레이어의 **측근 NPC(가신·참모·부하 지휘관)**가 보고하거나 회의를 여는 장면으로 시작
- 시나리오 인물 목록의 NPC를 우선 활용. 없으면 플레이어 세력에 자연스러운 가신을 새로 설정
- 상황 설명을 직접 나열하지 말고, **대화와 묘사** 속에서 자연스럽게 전달
- 주요 세력 동향·위협·기회를 장면 안에 녹여낼 것

### 선택지
- 장면 말미에 `**결정 기로**` 이후 3개의 구체적 행동 선택지 제시
- "상황을 파악한다" 같은 막연한 선택지 금지 — 목표·수단·대상이 명확해야 함

### 분량
400~700자 내외. 밀도 있게."""


def _troops_range(score: int, per_point: int) -> str:
    """strength_score → 추정 병력 범위 문자열 (±20%)"""
    base = score * per_point
    lo   = round(base * 0.8 / 500) * 500
    hi   = round(base * 1.2 / 500) * 500
    return f"약 {lo:,}~{hi:,}명"


def _event_condition_context(state: dict, current_year: int | None) -> dict:
    """이벤트 trigger_condition 평가에 쓰일 컨텍스트를 구성합니다."""
    locs        = state.get("locations", {})
    facs        = state.get("factions", {})
    prince_ids  = {fid for fid, f in facs.items() if f.get("type") == "faction"}
    controllers = {loc.get("controller") for loc in locs.values()}

    ctx: dict = {
        "year": current_year,
        "chapter": state.get("progress", {}).get("chapter"),
        "scene": state.get("progress", {}).get("scene"),
        "has_exiled_prince": any(
            pid not in controllers and (facs.get(pid, {}).get("battle_damage", 0) > 0)
            for pid in prince_ids
        ),
    }
    protagonist = state.get("protagonist")
    if prince_ids:
        ctx["active_princes"] = sum(1 for pid in prince_ids if pid != protagonist)

    # faction_vars 세력: {id}_defeated, {id}_strength 변수 추가
    faction_vars = (state.get("eventContext") or {}).get("faction_vars", [])
    for fid in faction_vars:
        f = facs.get(fid, {})
        ctx[f"{fid}_defeated"] = bool(f.get("defeated", False))
        ctx[f"{fid}_strength"] = max(0, (f.get("strength_score") or 0) - (f.get("battle_damage") or 0))

    # location_vars 거점: {id}_contested 변수 추가
    location_vars = (state.get("eventContext") or {}).get("location_vars", [])
    for lid in location_vars:
        loc = locs.get(lid, {})
        ctx[f"{lid}_contested"] = (loc.get("controller", "") == "contested")

    # 플레이어 세력 유효 전력
    if protagonist:
        chars = state.get("characters", {})
        pc    = chars.get(protagonist, {})
        pfid  = pc.get("faction_id") or (protagonist if protagonist in facs else None)
        pf    = facs.get(pfid, {}) if pfid else {}
        ctx["player_strength"] = max(0, (pf.get("strength_score") or 0) - (pf.get("battle_damage") or 0))

    # 모든 세력의 외교 수치: {fid}_score
    for fid, f in facs.items():
        score = f.get("diplomacy_score")
        if score is not None:
            ctx[f"{fid}_score"] = int(score)

    # 저장된 이벤트 상태에서 trigger_year 변수 추가
    stored_event_states = state.get("eventStates", {})
    for eid, ev_data in stored_event_states.items():
        ty = ev_data.get("trigger_year") if isinstance(ev_data, dict) else None
        if ty is not None:
            ctx[f"{eid}_trigger_year"] = ty

    # 이벤트 상태 플래그: {event_id}_active, {event_id}_ended
    for ev in state.get("events", []):
        eid = ev.get("id")
        if not eid:
            continue
        triggered = _evaluate_event_condition(_event_condition_expr(ev), ctx)
        ended     = bool(ev.get("end_condition")) and _evaluate_event_condition(ev["end_condition"], ctx)
        ctx[f"{eid}_active"] = triggered and not ended
        ctx[f"{eid}_ended"]  = ended

    return ctx


def _event_condition_expr(ev: dict) -> str | None:
    """신규 trigger_condition 또는 레거시 trigger_year를 조건식으로 정규화합니다."""
    cond = ev.get("trigger_condition")
    if isinstance(cond, str) and cond.strip():
        return cond.strip()
    if ev.get("trigger_year") is not None:
        return f"year >= {int(ev['trigger_year'])}"
    return None


def _coerce_condition_value(token: str, ctx: dict):
    token = token.strip()
    if token in ctx:
        return ctx[token]
    if re.fullmatch(r"-?\d+", token):
        return int(token)
    if (token.startswith('"') and token.endswith('"')) or (token.startswith("'") and token.endswith("'")):
        return token[1:-1]
    if token.lower() == "true":
        return True
    if token.lower() == "false":
        return False
    return None


def _eval_condition_atom(atom: str, ctx: dict) -> bool:
    atom = atom.strip()
    if not atom:
        return True

    m = re.fullmatch(r"(.+?)\s*(>=|<=|==|!=|>|<)\s*(.+)", atom)
    if m:
        left  = _coerce_condition_value(m.group(1), ctx)
        op    = m.group(2)
        right = _coerce_condition_value(m.group(3), ctx)
        if left is None or right is None:
            return False
        if op == ">=":
            return left >= right
        if op == "<=":
            return left <= right
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op == ">":
            return left > right
        if op == "<":
            return left < right

    val = _coerce_condition_value(atom, ctx)
    return bool(val) if val is not None else False


def _evaluate_event_condition(expression: str | None, ctx: dict) -> bool:
    """간단한 불리언 식을 평가합니다. 지원: and/or, 비교식, 단일 플래그."""
    if expression is None:
        return True

    expr = expression.strip()
    if not expr:
        return True

    or_parts = [part.strip() for part in re.split(r"\s*(?:\|\||\bor\b)\s*", expr, flags=re.IGNORECASE) if part.strip()]
    if len(or_parts) > 1:
        return any(_evaluate_event_condition(part, ctx) for part in or_parts)

    and_parts = [part.strip() for part in re.split(r"\s*(?:&&|\band\b)\s*", expr, flags=re.IGNORECASE) if part.strip()]
    if len(and_parts) > 1:
        return all(_evaluate_event_condition(part, ctx) for part in and_parts)

    return _eval_condition_atom(expr, ctx)


def _extract_trigger_year(ev: dict) -> int | None:
    """future_events 표시에 쓸 기준 연도를 추출합니다."""
    if ev.get("trigger_year") is not None:
        return int(ev["trigger_year"])

    cond = ev.get("trigger_condition")
    if not isinstance(cond, str) or not cond.strip():
        return None
    if re.search(r"(?:\|\||\bor\b)", cond, flags=re.IGNORECASE):
        return None

    atoms = [part.strip() for part in re.split(r"\s*(?:&&|\band\b)\s*", cond, flags=re.IGNORECASE) if part.strip()]
    for atom in atoms:
        m = re.fullmatch(r"year\s*(>=|>|==)\s*(-?\d+)", atom, flags=re.IGNORECASE)
        if m:
            year = int(m.group(2))
            return year + 1 if m.group(1) == ">" else year
        m = re.fullmatch(r"(-?\d+)\s*(<=|<|==)\s*year", atom, flags=re.IGNORECASE)
        if m:
            year = int(m.group(1))
            return year + 1 if m.group(2) == "<" else year
    return None


def _ev_state(val) -> str | None:
    """eventStates 값에서 state 문자열을 추출합니다 (구 형식 str / 신 형식 dict 호환)."""
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        return val.get("state")
    return None


def strip_event_states(states: dict) -> dict:
    """내부 전용 키(_로 시작)를 제거해 직렬화 가능한 형태로 반환합니다."""
    result: dict = {}
    for eid, data in states.items():
        if isinstance(data, dict):
            result[eid] = {k: v for k, v in data.items() if not k.startswith("_")}
        else:
            result[eid] = data
    return result


def compute_event_states(state: dict) -> dict:
    """
    이벤트 상태를 계산합니다.

    반환값: {event_id: {"state": "active"|"ended", "trigger_year": int|None, "end_pathway": str|None}}
    내부 전용 키 "_end_pathway_data"는 detect_event_transitions 에서 사용 후 strip_event_states로 제거합니다.
    chain_trigger가 있는 end_pathway 발동 시 해당 이벤트가 force_active에 추가되어 2패스로 처리됩니다.
    """
    events = state.get("events", [])
    stored_states = state.get("eventStates", {})
    ts = state.get("progress", {}).get("timestamp", "")
    m = re.search(r'(\d{3,4})년', ts)
    current_year = int(m.group(1)) if m else None
    cond_ctx = _event_condition_context(state, current_year)

    ev_map = {ev["id"]: ev for ev in events if ev.get("id")}
    new_states: dict = {}
    force_active: set = set()

    def _prev_state(eid: str) -> str | None:
        return _ev_state(stored_states.get(eid))

    def _prev_trigger_year(eid: str) -> int | None:
        d = stored_states.get(eid)
        return d.get("trigger_year") if isinstance(d, dict) else None

    def _process_event(eid: str, is_forced: bool = False) -> None:
        ev = ev_map.get(eid)
        if not ev:
            return
        prev_st = _prev_state(eid)
        prev_ty = _prev_trigger_year(eid)

        triggered = is_forced or _evaluate_event_condition(_event_condition_expr(ev), cond_ctx)
        if not triggered:
            return

        trigger_year = prev_ty if prev_st == "active" else current_year

        # end_pathways: 첫 번째로 조건 충족되는 경로 사용
        pathway_hit = None
        pathways = ev.get("end_pathways", [])
        if pathways:
            for pw in pathways:
                if _evaluate_event_condition(pw.get("condition"), cond_ctx):
                    pathway_hit = pw
                    break
        else:
            # 단일 end_condition 방식 (기존 호환)
            end_cond = ev.get("end_condition")
            if end_cond and _evaluate_event_condition(end_cond, cond_ctx):
                pathway_hit = {
                    "id": "_end",
                    "on_end_prompt": ev.get("on_end_prompt"),
                    "chain_trigger": None,
                }

        if pathway_hit:
            new_states[eid] = {
                "state":        "ended",
                "trigger_year": trigger_year,
                "end_pathway":  pathway_hit.get("id"),
                "_end_pathway_data": pathway_hit,  # strip_event_states로 제거됨
            }
            chain = pathway_hit.get("chain_trigger")
            if chain:
                force_active.add(chain)
        else:
            # active_chains: 활성 중 조건이 충족되면 한 번만 발화하는 부속 체인
            prev_fired: set[str] = set(
                (stored_states.get(eid) or {}).get("fired_chains", [])
                if isinstance(stored_states.get(eid), dict) else []
            )
            new_fired = set(prev_fired)
            for ac in ev.get("active_chains", []):
                cid = ac.get("chain_trigger")
                if cid and cid not in prev_fired:
                    if _evaluate_event_condition(ac.get("condition"), cond_ctx):
                        force_active.add(cid)
                        new_fired.add(cid)
            entry: dict = {"state": "active", "trigger_year": trigger_year}
            if new_fired:
                entry["fired_chains"] = sorted(new_fired)
            new_states[eid] = entry

    # 1패스: 모든 이벤트 정상 처리
    for ev in events:
        eid = ev.get("id")
        if eid:
            _process_event(eid)

    # 2패스: chain_trigger로 강제 발동된 이벤트 (아직 미처리된 것만)
    for eid in force_active:
        if eid not in new_states:
            _process_event(eid, is_forced=True)

    return new_states


def detect_event_transitions(
    stored: dict,
    current: dict,
    events: list[dict],
) -> tuple[list[tuple], list[tuple]]:
    """신규 활성화·종료 이벤트를 검출합니다.
    Returns (newly_active, newly_ended) — 각각 (event_dict, state_data) 튜플 리스트.
    """
    ev_map = {ev["id"]: ev for ev in events if ev.get("id")}
    newly_active: list[tuple] = []
    newly_ended:  list[tuple] = []
    for eid, cur_data in current.items():
        cur_state  = _ev_state(cur_data)
        prev_state = _ev_state(stored.get(eid))
        ev = ev_map.get(eid)
        if not ev:
            continue
        if cur_state == "active" and prev_state != "active":
            newly_active.append((ev, cur_data))
        elif cur_state == "ended" and prev_state == "active":
            newly_ended.append((ev, cur_data))
    return newly_active, newly_ended


def collect_transition_effects(
    newly_active: list[tuple],
    newly_ended:  list[tuple],
    state: dict,
    protagonist_id: str | None = None,
) -> dict:
    """이벤트 전환 시 LLM 없이 시스템이 직접 적용할 상태 변경을 수집합니다.

    Returns: {
        "faction_strength_changes":     [{id, delta}, ...],
        "character_disposition_changes": [{id, disposition}, ...],
        "faction_diplomacy_changes":    [{id, delta}, ...],
    }
    각 항목의 "condition" 필드가 있으면 현재 컨텍스트로 평가 후 조건 불충족 시 건너뜁니다.
    """
    ts = state.get("progress", {}).get("timestamp", "")
    m  = re.search(r'(\d{3,4})년', ts)
    current_year = int(m.group(1)) if m else None
    cond_ctx = _event_condition_context(state, current_year)

    faction_strength:  list[dict] = []
    char_disposition:  list[dict] = []
    faction_diplomacy: list[dict] = []

    def _applies(ev: dict) -> bool:
        po = ev.get("protagonist_only")
        return not po or not protagonist_id or protagonist_id in po

    def _apply(effects: dict):
        for item in effects.get("faction_strength_changes", []):
            if item.get("condition") and not _evaluate_event_condition(item["condition"], cond_ctx):
                continue
            faction_strength.append({"id": item["id"], "delta": item["delta"]})
        for item in effects.get("character_disposition_changes", []):
            if item.get("condition") and not _evaluate_event_condition(item["condition"], cond_ctx):
                continue
            char_disposition.append({"id": item["id"], "disposition": item["disposition"]})
        for item in effects.get("faction_diplomacy_changes", []):
            if item.get("condition") and not _evaluate_event_condition(item["condition"], cond_ctx):
                continue
            faction_diplomacy.append({"id": item["id"], "delta": item["delta"]})

    for ev, _ in newly_active:
        if not _applies(ev):
            continue
        effects = ev.get("on_trigger_effects")
        if effects:
            _apply(effects)

    for ev, state_data in newly_ended:
        if not _applies(ev):
            continue
        pathway_data = state_data.get("_end_pathway_data") if isinstance(state_data, dict) else None
        effects = (pathway_data.get("state_effects") if pathway_data else None) or ev.get("on_end_effects")
        if effects:
            _apply(effects)

    result: dict = {}
    if faction_strength:
        result["faction_strength_changes"] = faction_strength
    if char_disposition:
        result["character_disposition_changes"] = char_disposition
    if faction_diplomacy:
        result["faction_diplomacy_changes"] = faction_diplomacy
    return result


def build_event_transition_prompt(
    newly_active: list[tuple],
    newly_ended:  list[tuple],
    protagonist_id: str | None = None,
) -> str:
    """이번 턴 이벤트 전환을 LLM 서술에 반영하도록 지시하는 프롬프트를 반환합니다."""
    def _applies(ev: dict) -> bool:
        po = ev.get("protagonist_only")
        return not po or not protagonist_id or protagonist_id in po

    active_ok = [(ev, d) for ev, d in newly_active if _applies(ev)]
    ended_ok  = [(ev, d) for ev, d in newly_ended  if _applies(ev)]
    if not active_ok and not ended_ok:
        return ""

    lines = ["\n\n---\n## 이번 턴 이벤트 전환 (서술 반영 필수)"]
    for ev, _ in active_ok:
        prompt = ev.get("on_trigger_prompt") or f'"{ev.get("name", ev["id"])}" 이벤트가 발동됐다. 이번 서술에 자연스럽게 반영하라.'
        lines.append(f"\n### 발동: {ev.get('name', ev['id'])}\n{prompt}")
    for ev, state_data in ended_ok:
        # end_pathway가 있으면 pathway의 on_end_prompt 우선 사용
        pathway_data = state_data.get("_end_pathway_data") if isinstance(state_data, dict) else None
        prompt = (
            (pathway_data.get("on_end_prompt") if pathway_data else None)
            or ev.get("on_end_prompt")
            or f'"{ev.get("name", ev["id"])}" 이벤트가 해소됐다. 이번 서술에 자연스럽게 반영하라.'
        )
        lines.append(f"\n### 해소: {ev.get('name', ev['id'])}\n{prompt}")
    return "\n".join(lines)


def build_scenario_context(state: dict, scenario_prompts: dict | None = None) -> str:
    """state에서 시나리오 정보를 추출해 시스템 프롬프트 끝에 추가합니다."""
    protagonist_id = state.get("protagonist", "")
    lines = [
        "",
        "---",
        "# 현재 시나리오 상태 (엔진이 자동 주입)",
        f"시나리오: {state.get('scenarioTitle', '불명')}",
    ]

    if scenario_prompts:
        global_p = scenario_prompts.get("global", "").strip()
        char_p   = scenario_prompts.get("characters", {}).get(protagonist_id, "").strip()
        if global_p or char_p:
            lines.append("\n## 시나리오 특수 지시")
            if global_p:
                lines.append(global_p)
            if char_p:
                lines.append("\n### 캐릭터 전용 지시")
                lines.append(char_p)

    chars     = state.get("characters", {})
    factions  = state.get("factions", {})
    tpp            = state.get("troopsPerPoint")  # troops per strength_score point
    if protagonist_id and protagonist_id in chars:
        c = chars[protagonist_id]
        troops = c.get("troops_count")
        # troops_count가 없으면 소속 세력 strength_score로 추정
        if troops is not None:
            troops_str = f" / 병력 {troops:,}명"
        else:
            pf = factions.get(c.get("faction_id") or protagonist_id) if factions else None
            if pf:
                fa = pf.get("field_army")
                if fa is not None:
                    troops_str = f" / 야전군 {fa:,}명"
                elif pf.get("strength_score") is not None and tpp:
                    s_eff = pf["strength_score"] - pf.get("battle_damage", 0)
                    troops_str = f" / 병력 {_troops_range(int(s_eff), tpp)}"
                else:
                    troops_str = ""
            else:
                troops_str = ""
        lines.append(
            f"플레이어: {c.get('name', protagonist_id)}"
            + (f" / {c.get('title') or c.get('epithet', '')}" if c.get('title') or c.get('epithet') else "")
            + troops_str
        )

    active_factions = {fid: f for fid, f in factions.items() if not f.get("defeated")}
    if active_factions:
        lines.append("\n등장 세력:")
        for f in active_factions.values():
            note       = f.get("notes", "")
            note_short = note[:80] + "…" if len(note) > 80 else note
            dipl       = f.get("diplomacy_score")
            dipl_str   = f" [{int(dipl):+d}]" if dipl is not None else ""
            s_base     = f.get("strength_score")
            s_dmg      = f.get("battle_damage", 0)
            s_eff      = (s_base - s_dmg) if s_base is not None else None
            field_army = f.get("field_army")
            mult       = f.get("combat_multiplier", 1)
            if field_army is not None:
                if mult > 1:
                    total = field_army * mult
                    mult_str = f" (본국 증원 포함 최대 {total:,}명)"
                else:
                    mult_str = ""
                if s_base is not None and tpp:
                    str_str = f" [전력 {_troops_range(int(s_base), tpp)} / 야전군 {field_army:,}명{mult_str}]"
                else:
                    str_str = f" [야전군 {field_army:,}명{mult_str}]"
            else:
                str_str = (f" [병력 {_troops_range(int(s_eff), tpp)}]"
                           if s_eff is not None and tpp else "")
            lines.append(
                f"  - {f.get('name', '?')} | {f.get('disposition', '?')}{dipl_str}{str_str}"
                + (f"\n    {note_short}" if note_short else "")
            )

    locations = state.get("locations", {})
    if locations:
        lines.append("\n주요 거점:")
        for loc in locations.values():
            controller = loc.get("controller", "?")
            if controller in factions:
                controller = factions[controller].get("name", controller)
            garrison = loc.get("garrison")
            garrison_str = f" | 수비대 {garrison:,}명" if garrison else ""
            lines.append(f"  - {loc.get('name', '?')} | 지배: {controller}{garrison_str}")

    events       = state.get("events", [])
    ts           = state.get("progress", {}).get("timestamp", "")
    m            = re.search(r'(\d{3,4})년', ts)
    current_year = int(m.group(1)) if m else None

    cond_ctx = _event_condition_context(state, current_year)
    active_events = [
        ev for ev in events
        if _evaluate_event_condition(_event_condition_expr(ev), cond_ctx)
        and not (ev.get("end_condition") and _evaluate_event_condition(ev["end_condition"], cond_ctx))
    ]
    future_events = [
        ev for ev in events
        if (trigger_year := _extract_trigger_year(ev)) is not None
        and current_year is not None
        and current_year < trigger_year
    ]

    if active_events:
        lines.append("\n동시 진행 사건:")
        for ev in active_events:
            name   = ev.get("name", "?")
            region = ev.get("region", "")
            text   = ev.get("prompt") or ev.get("body", "")
            text_out = text if ev.get("prompt") else (text[:80] + "…" if len(text) > 80 else text)
            lines.append(
                f"  - {name}" + (f" ({region})" if region else "")
                + (f"\n    {text_out}" if text_out else "")
            )

    if future_events:
        lines.append("\n역사적 예정 사건 (내러티브 참고 — UI 미표시):")
        for ev in future_events:
            name    = ev.get("name", "?")
            trigger = _extract_trigger_year(ev) or "?"
            text    = ev.get("prompt") or ev.get("body", "")
            text_short = text[:80] + "…" if len(text) > 80 else text
            lines.append(
                f"  - [{trigger}년 예정] {name}"
                + (f"\n    {text_short}" if text_short else "")
            )

    weather = state.get("weather")
    if weather and weather != "clear":
        _WEATHER_LABELS = {
            "rain": "강우", "heavy_rain": "폭우", "snow": "강설",
            "blizzard": "눈보라", "heat": "폭염", "fog": "짙은 안개", "storm": "폭풍",
        }
        lines.append(f"\n현재 기상: {_WEATHER_LABELS.get(weather, weather)}")

    progress      = state.get("progress", {})
    chapter       = progress.get("chapter", 1)
    scene         = progress.get("scene", 1)
    is_end        = progress.get("isChapterEnd", False)
    ts            = progress.get("timestamp", "")
    player_loc_id = progress.get("playerLocationId")
    player_loc_label = ""
    if player_loc_id:
        loc_entry = locations.get(player_loc_id, {})
        player_loc_label = f" | 플레이어 거점: {loc_entry.get('name', player_loc_id)} ({player_loc_id})"
    lines.append(
        f"\n현재 위치: {chapter}장 SCENE {scene}"
        + (" (장 종결 후 대기 중)" if is_end else "")
        + (f" / {ts}" if ts else "")
        + player_loc_label
    )

    combat_state = state.get("combatState")
    if combat_state and combat_state.get("active"):
        player_fid  = combat_state.get("player_faction_id", "")
        enemy_fid   = combat_state.get("enemy_faction_id", "")
        player_name = factions.get(player_fid, {}).get("name", player_fid) if factions else player_fid
        enemy_name  = factions.get(enemy_fid,  {}).get("name", enemy_fid)  if factions else enemy_fid
        phase       = combat_state.get("phase_number", 1)
        p_strength  = combat_state.get("player_strength", "?")
        e_strength  = combat_state.get("enemy_strength", "?")
        enemy_next  = combat_state.get("enemy_next_action") or "아직 예고되지 않음"
        is_siege    = combat_state.get("is_siege", False)
        garrison    = combat_state.get("siege_garrison", 0)

        if is_siege:
            siege_lid   = combat_state.get("siege_location_id", "")
            locs        = state.get("locations", {})
            loc_name    = locs.get(siege_lid, {}).get("name", siege_lid) if locs else siege_lid
            lines.append(
                f"\n## 공성전 진행 중\n"
                f"{player_name} → {loc_name} 공성"
                f" | 다음 페이즈 {phase}"
                f" | 아군 전력 {p_strength} / 수비대 {garrison:,}명 (실효 전력 {e_strength})"
                f"\n수비대 예고 행동: {enemy_next}"
            )
        else:
            lines.append(
                f"\n## 전투 진행 중\n"
                f"{player_name} vs {enemy_name}"
                f" | 다음 페이즈 {phase}"
                f" | 아군 전력 {p_strength} / 적군 전력 {e_strength}"
                f"\n적군 예고 행동: {enemy_next}"
            )

    return "\n".join(lines)


def build_opening_context(state: dict) -> str:
    """오프닝 전용: 기존 등장 인물을 LLM에 전달합니다."""
    chars          = state.get("characters", {})
    protagonist_id = state.get("protagonist", "")
    lines          = ["\n\n---\n## 오프닝 장면 등장 인물"]

    supporting = [c for c in chars.values() if c.get("id") != protagonist_id]
    if supporting:
        lines.append("\n### 기존 등장 인물 (우선 활용)")
        for c in supporting:
            name    = c.get("name", "?")
            epithet = c.get("epithet") or c.get("title") or ""
            desc    = c.get("desc") or c.get("notes") or ""
            disp    = c.get("disposition", "")
            lines.append(f"  - {name}({epithet}) [{disp}]: {desc[:120]}")

    lines.append("\n위 인물들의 성격·역할·성향을 장면에 반영하시오.")
    lines.append("장면에 등장한 인물은 반드시 응답 끝 [STATE_UPDATE]의 new_characters에 포함할 것.")
    lines.append("이미 '기존 등장 인물'로 표시된 인물은 new_characters에 포함하지 않는다.")
    return "\n".join(lines)
