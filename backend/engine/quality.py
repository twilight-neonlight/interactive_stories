"""
engine/quality.py — 행동 전략 품질 평가

LLM을 사용해 플레이어의 선택이 현재 전략적 맥락에서 얼마나 우수한지
체스 기보 표기법(!!/!/=/??/??)으로 평가하고 판정 수정치로 변환합니다.
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

_EVAL_SYSTEM = """\
전략 평가자. 현재 상황을 기반으로 플레이어의 행동이 얼마나 전략적으로 적절한지 평가한다.
체스 기보 기호를 사용하며, 평범한 선택은 =로 평가한다.

!! 절묘한 수 — 상황의 핵심을 꿰뚫는 창의적·결정적 선택. 드물다.
!  좋은 수 — 상황에 잘 맞고 전략적으로 유효한 선택
=  평이한 수 — 무난하지만 특별한 강약이 없는 선택 (가장 일반적)
?  의문스러운 수 — 비효율적이거나 더 나은 선택이 명백히 있음
?? 블런더 — 전략적으로 큰 실수, 상황을 심각하게 악화시키는 선택

JSON만 출력 (다른 텍스트 절대 금지):
{"quality": "!!"또는"!"또는"="또는"?"또는"??", "label": "평가 이유 (10자 이내)"}"""


def _build_eval_context(state: dict) -> str:
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

    if player_faction_id and player_faction_id in factions:
        pf = factions[player_faction_id]
        dmg = pf.get("battle_damage", 0)
        eff = pf.get("strength_score", 0) - dmg
        lines.append(
            f"\n[플레이어] {pf.get('name', player_faction_id)} "
            f"(잠재 전력 {pf.get('strength_score', '?')}"
            + (f", 전투 피해 -{dmg}" if dmg else "") + ")"
        )
        if pf.get("notes"):
            lines.append(f"  특성: {pf['notes']}")

    other_factions = [f for fid, f in factions.items() if fid != player_faction_id]
    if other_factions:
        lines.append("\n[다른 세력]")
        for f in other_factions:
            disp  = f.get("disposition", "중립")
            notes = (f.get("notes") or "")[:60]
            lines.append(
                f"  [{disp}] {f.get('name', '?')} "
                f"(잠재 전력 {f.get('strength_score', '?')})"
                + (f": {notes}" if notes else "")
            )

    return "\n".join(lines)


async def evaluate_action_quality(command: str, state: dict) -> tuple[str, int] | None:
    """
    플레이어 행동의 전략적 품질을 LLM으로 평가합니다.
    평이한 선택(=)이면 None, 그 외엔 (레이블, 수정치)를 반환합니다.
    평가 실패 시에도 None을 반환해 판정에 영향을 주지 않습니다.
    """
    context  = _build_eval_context(state)
    user_msg = f"{context}\n\n[플레이어 행동]\n{command}"

    try:
        raw  = await call_gemini([
            {"role": "system", "content": _EVAL_SYSTEM},
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
