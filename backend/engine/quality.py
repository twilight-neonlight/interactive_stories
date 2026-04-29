"""
engine/quality.py — 행동 전략 품질 평가

LLM을 사용해 플레이어의 선택이 현재 전략적 맥락에서 얼마나 우수한지
체스 기보 표기법(!!/!/=/??/??)으로 평가하고 판정 수정치로 변환합니다.

행동 유형별로 평가 기준을 달리합니다:
  군사 — 병력 우위, 아군 지원 여부, 타이밍·기습 가능성 (지형은 resolver에서 별도 처리)
  외교 — 관계도, 협상 레버리지, 상대의 동기
  첩보 — 정보망 수준, 목표의 취약점, 작전 은밀성
"""

import json
from gemini_client import call_gemini

_QUALITY_VALUES: dict[str, int] = {
    "!!": +20,
    "!":  +10,
    "=":    0,
    "?":  -10,
    "??": -20,
}

_BASE_INSTRUCTIONS = """\
체스 기보 기호를 사용하며, 평범한 선택은 =로 평가한다.

!! 절묘한 수 — 상황의 핵심을 꿰뚫는 창의적·결정적 선택. 드물다.
!  좋은 수 — 상황에 잘 맞고 전략적으로 유효한 선택
=  평이한 수 — 무난하지만 특별한 강약이 없는 선택 (가장 일반적)
?  의문스러운 수 — 비효율적이거나 더 나은 선택이 명백히 있음
?? 블런더 — 전략적으로 큰 실수, 상황을 심각하게 악화시키는 선택

JSON만 출력 (다른 텍스트 절대 금지):
{"quality": "!!"또는"!"또는"="또는"?"또는"??", "label": "평가 이유 (10자 이내)"}"""

_SYSTEM_MILITARY = f"""\
군사 전략 평가자. 플레이어의 군사 행동이 현재 전력 상황에서 얼마나 적절한지 판단한다.
평가 기준: 아군 대비 적군 전력 우위, 아군 세력의 지원 여부, 기습·타이밍의 적절성,
현재 피해 상태, 병력 소모 대비 기대 효과. 지형 이점은 별도 처리되므로 고려하지 않는다.
{_BASE_INSTRUCTIONS}"""

_SYSTEM_DIPLOMATIC = f"""\
외교 전략 평가자. 플레이어의 외교 행동이 현재 관계 맥락에서 얼마나 적절한지 판단한다.
평가 기준: 대상 세력과의 현재 관계도, 플레이어가 제시할 수 있는 레버리지(공동 이해관계·위협·이익),
상대의 현재 동기와 취약점, 요청 내용과 관계도의 균형.
{_BASE_INSTRUCTIONS}"""

_SYSTEM_INTRIGUE = f"""\
첩보·모략 전략 평가자. 플레이어의 첩보 행동이 현재 상황에서 얼마나 적절한지 판단한다.
평가 기준: 목표 세력의 취약점과 내부 불안정성, 작전의 은밀성과 역탐지 위험,
현재 관계도(관계가 좋을수록 내통 공작이 쉬움), 실행 타이밍의 적절성.
{_BASE_INSTRUCTIONS}"""

_SYSTEM_BY_TYPE = {
    "military": _SYSTEM_MILITARY,
    "surprise": _SYSTEM_MILITARY,
    "defense":  _SYSTEM_MILITARY,
    "diplomatic": _SYSTEM_DIPLOMATIC,
    "intrigue":   _SYSTEM_INTRIGUE,
}


def _build_military_context(state: dict, player_faction_id: str | None) -> list[str]:
    factions = state.get("factions", {})
    lines = []

    if player_faction_id and player_faction_id in factions:
        pf         = factions[player_faction_id]
        field_army = pf.get("field_army")
        if field_army is not None:
            lines.append(f"\n[아군] {pf.get('name', player_faction_id)} 야전군 {field_army:,}명")
        else:
            dmg = pf.get("battle_damage", 0)
            eff = pf.get("strength_score", 0) - dmg
            lines.append(
                f"\n[아군] {pf.get('name', player_faction_id)} "
                f"실효 전력 {eff} (잠재 {pf.get('strength_score', '?')}"
                + (f", 전투 피해 -{dmg}" if dmg else "") + ")"
            )

    enemy = [f for fid, f in factions.items()
             if fid != player_faction_id and f.get("disposition") == "적대"]
    ally  = [f for fid, f in factions.items()
             if fid != player_faction_id and f.get("disposition") == "우호"]

    def _faction_army_str(f: dict) -> str:
        fa   = f.get("field_army")
        mult = f.get("combat_multiplier", 1)
        if fa is not None:
            suffix = f" (본국 증원 포함 최대 {fa * mult:,}명)" if mult > 1 else ""
            return f"야전군 {fa:,}명{suffix}"
        dmg = f.get("battle_damage", 0)
        eff = f.get("strength_score", 0) - dmg
        return f"실효 전력 {eff}"

    if enemy:
        lines.append("\n[적군]")
        for f in enemy:
            lines.append(f"  {f.get('name', '?')} {_faction_army_str(f)}")

    if ally:
        lines.append("\n[우군]")
        for f in ally:
            field_army = f.get("field_army")
            if field_army is not None:
                lines.append(f"  {f.get('name', '?')} {_faction_army_str(f)}")
            else:
                lines.append(f"  {f.get('name', '?')} 잠재 전력 {f.get('strength_score', '?')}")

    return lines


def _build_diplomatic_context(state: dict, player_faction_id: str | None) -> list[str]:
    factions   = state.get("factions", {})
    diplomacy  = state.get("diplomacy", {})
    lines = []

    if player_faction_id and player_faction_id in factions:
        pf = factions[player_faction_id]
        lines.append(f"\n[아군] {pf.get('name', player_faction_id)}")

    other = [f for fid, f in factions.items() if fid != player_faction_id]
    if other:
        lines.append("\n[대상 세력]")
        for f in other:
            fid   = f.get("id", "")
            score = diplomacy.get(fid, 0) if isinstance(diplomacy, dict) else 0
            disp  = f.get("disposition", "중립")
            lines.append(
                f"  [{disp}] {f.get('name', '?')} "
                f"관계도 {score:+d}"
                + (f" | {f.get('notes', '')[:60]}" if f.get("notes") else "")
            )

    return lines


def _build_intrigue_context(state: dict, player_faction_id: str | None) -> list[str]:
    factions  = state.get("factions", {})
    diplomacy = state.get("diplomacy", {})
    lines = []

    if player_faction_id and player_faction_id in factions:
        pf = factions[player_faction_id]
        lines.append(f"\n[아군] {pf.get('name', player_faction_id)}")

    other = [f for fid, f in factions.items() if fid != player_faction_id]
    if other:
        lines.append("\n[세력 현황]")
        for f in other:
            fid        = f.get("id", "")
            score      = diplomacy.get(fid, 0) if isinstance(diplomacy, dict) else 0
            disp       = f.get("disposition", "중립")
            field_army = f.get("field_army")
            if field_army is not None:
                strength_str = f"야전군 {field_army:,}명"
            else:
                dmg = f.get("battle_damage", 0)
                eff = f.get("strength_score", 0) - dmg
                strength_str = f"실효 전력 {eff}"
            lines.append(f"  [{disp}] {f.get('name', '?')} {strength_str}, 관계도 {score:+d}")

    return lines


def _build_eval_context(state: dict, action_type: str) -> str:
    factions       = state.get("factions", {})
    chars          = state.get("characters", {})
    protagonist_id = state.get("protagonist")

    player_char       = chars.get(protagonist_id, {}) if protagonist_id else {}
    player_faction_id = (player_char.get("faction_id") or player_char.get("faction")
                         or (protagonist_id if protagonist_id in factions else None))

    lines = []
    progress = state.get("progress", {})
    if progress.get("chapter"):
        lines.append(f"현재: {progress['chapter']}장 {progress.get('scene', 1)}씬")

    if action_type in {"military", "surprise", "defense"}:
        lines += _build_military_context(state, player_faction_id)
    elif action_type == "diplomatic":
        lines += _build_diplomatic_context(state, player_faction_id)
    elif action_type == "intrigue":
        lines += _build_intrigue_context(state, player_faction_id)

    return "\n".join(lines)


async def evaluate_action_quality(command: str, state: dict,
                                   action_type: str = "general") -> tuple[str, int] | None:
    """
    플레이어 행동의 전략적 품질을 LLM으로 평가합니다.
    평이한 선택(=)이면 None, 그 외엔 (레이블, 수정치)를 반환합니다.
    평가 실패 시에도 None을 반환해 판정에 영향을 주지 않습니다.
    """
    system  = _SYSTEM_BY_TYPE.get(action_type, _SYSTEM_MILITARY)
    context = _build_eval_context(state, action_type)
    user_msg = f"{context}\n\n[플레이어 행동]\n{command}"

    try:
        raw  = await call_gemini([
            {"role": "system", "content": system},
            {"role": "user",   "content": user_msg},
        ])
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1].lstrip("json").strip()
        data = json.loads(text)

        q = data.get("quality", "=")
        v = _QUALITY_VALUES.get(q, 0)
        if v == 0:
            return None

        short = (data.get("label") or "").strip()[:12]
        label = f"{short} ({q})" if short else q
        return (label, v)
    except Exception:
        return None
