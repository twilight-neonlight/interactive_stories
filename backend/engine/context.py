"""
engine/context.py — LLM 시나리오 컨텍스트 빌더

현재 게임 상태를 시스템 프롬프트에 주입할 텍스트로 변환합니다.
오프닝 전용 NPC 컨텍스트 빌더도 포함합니다.
"""


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
- 장면 말미에 `**결정 기로**` 이후 **3~4개의 구체적 행동 선택지** 제시
- "상황을 파악한다" 같은 막연한 선택지 금지 — 목표·수단·대상이 명확해야 함

### 분량
400~700자 내외. 밀도 있게."""


def build_scenario_context(state: dict) -> str:
    """state에서 시나리오 정보를 추출해 시스템 프롬프트 끝에 추가합니다."""
    lines = [
        "",
        "---",
        "# 현재 시나리오 상태 (엔진이 자동 주입)",
        f"시나리오: {state.get('scenarioTitle', '불명')}",
    ]

    protagonist_id = state.get("protagonist")
    chars = state.get("characters", {})
    if protagonist_id and protagonist_id in chars:
        c = chars[protagonist_id]
        troops = c.get("troops_count")
        troops_str = f" / 병력 {troops:,}명" if troops is not None else ""
        lines.append(
            f"플레이어: {c.get('name', protagonist_id)}"
            + (f" / {c.get('title') or c.get('epithet', '')}" if c.get('title') or c.get('epithet') else "")
            + troops_str
        )

    factions = state.get("factions", {})
    if factions:
        lines.append("\n등장 세력:")
        for f in factions.values():
            note       = f.get("notes", "")
            note_short = note[:80] + "…" if len(note) > 80 else note
            dipl       = f.get("diplomacy_score")
            dipl_str   = f" [{int(dipl):+d}]" if dipl is not None else ""
            s_base     = f.get("strength_score")
            s_dmg      = f.get("battle_damage", 0)
            str_str    = (f" [{int(s_base)}" + (f"-{int(s_dmg)}dmg" if s_dmg else "") + "]"
                          if s_base is not None else "")
            lines.append(
                f"  - {f.get('name', '?')} | {f.get('disposition', '?')}{dipl_str} | {f.get('strength', '?')}{str_str}"
                + (f"\n    {note_short}" if note_short else "")
            )

    locations = state.get("locations", {})
    if locations:
        lines.append("\n주요 거점:")
        for loc in locations.values():
            controller = loc.get("controller", "?")
            if controller in factions:
                controller = factions[controller].get("name", controller)
            lines.append(f"  - {loc.get('name', '?')} | 지배: {controller}")

    events = state.get("events", [])
    if events:
        lines.append("\n동시 진행 사건:")
        for ev in events:
            name       = ev.get("name", "?")
            region     = ev.get("region", "")
            body       = ev.get("body", "")
            body_short = body[:80] + "…" if len(body) > 80 else body
            lines.append(
                f"  - {name}" + (f" ({region})" if region else "")
                + (f"\n    {body_short}" if body_short else "")
            )

    progress = state.get("progress", {})
    chapter  = progress.get("chapter", 1)
    scene    = progress.get("scene", 1)
    is_end   = progress.get("isChapterEnd", False)
    ts       = progress.get("timestamp", "")
    lines.append(
        f"\n현재 위치: {chapter}장 SCENE {scene}"
        + (" (장 종결 후 대기 중)" if is_end else "")
        + (f" / {ts}" if ts else "")
    )

    return "\n".join(lines)


def build_opening_npc_context(state: dict, npc_pool: dict) -> str:
    """오프닝 전용: 등장 인물 + NPC 풀을 LLM에 전달합니다."""
    chars          = state.get("characters", {})
    protagonist_id = state.get("protagonist", "")
    lines          = ["\n\n---\n## 오프닝 장면 등장 가능 인물"]

    supporting = [c for c in chars.values() if c.get("id") != protagonist_id]
    if supporting:
        lines.append("\n### 기존 등장 인물 (우선 활용)")
        for c in supporting:
            name    = c.get("name", "?")
            epithet = c.get("epithet") or c.get("title") or ""
            desc    = c.get("desc") or c.get("notes") or ""
            disp    = c.get("disposition", "")
            lines.append(f"  - {name}({epithet}) [{disp}]: {desc[:120]}")

    pool_npcs = npc_pool.get("default", []) if isinstance(npc_pool, dict) else []
    eligible  = [
        n for n in pool_npcs
        if n.get("start_eligible", True) and n["id"] not in chars and n["id"] != protagonist_id
    ]
    if eligible:
        lines.append("\n### NPC 풀 (장면에 등장 가능)")
        for n in sorted(eligible, key=lambda x: -x.get("weight", 0))[:8]:
            lines.append(
                f"  - {n['name']}({n.get('epithet', '')}) [weight {n.get('weight',0)}]: {n.get('desc','')[:120]}"
            )

    lines.append("\n위 인물들의 성격·역할·성향을 장면에 반영하시오.")
    lines.append("장면에 등장한 인물은 반드시 응답 끝 [STATE_UPDATE]의 new_characters에 포함할 것.")
    lines.append("이미 '기존 등장 인물'로 표시된 인물은 new_characters에 포함하지 않는다.")
    return "\n".join(lines)
