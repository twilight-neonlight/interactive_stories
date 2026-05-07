"""
engine/classifier.py — LLM 기반 행동 유형 분류

플레이어 명령 + 현재 상태를 Gemini에 전달해 행동 유형과 전투 지명을 반환합니다.
429 오류 시 gemini_client 레이어에서 재시도하며, 최종 실패 시 키워드 기반 폴백을 사용합니다.
"""

import json
from gemini_client import call_gemini_json
from engine.resolver import classify_action_type

_ACTION_TYPES = frozenset({
    "open_field",    # 야전 전투 (성벽 밖)
    "ambush",        # 기습·매복
    "defense",       # 야전 방어
    "siege_attack",  # 공성 (공격측)
    "siege_defense", # 수성 (방어측)
    "diplomatic",    # 외교·협상
    "intrigue",      # 첩보·모략
    "passive",       # 관찰·대기·이동
    "general",       # 기타
})

# 키워드 분류기 결과 → LLM 분류 유형 매핑 (폴백용)
_KW_TO_CLS: dict[str, str] = {
    "military":   "open_field",
    "surprise":   "ambush",
    "defense":    "defense",
    "diplomatic": "diplomatic",
    "intrigue":   "intrigue",
    "passive":    "passive",
    "general":    "general",
}

# LLM 분류 유형 → resolver 내부 action_type 매핑
CLS_TO_RESOLVER: dict[str, str] = {
    "open_field":    "military",
    "ambush":        "surprise",
    "defense":       "defense",
    "siege_attack":  "military",
    "siege_defense": "defense",
    "diplomatic":    "diplomatic",
    "intrigue":      "intrigue",
    "passive":       "passive",
    "general":       "general",
}

_SYSTEM = """\
전략 게임 행동 분류기. 플레이어 명령과 현재 상황을 보고 행동 유형을 판단한다.

행동 유형 정의:
- open_field: 야전 전투 (성벽·요새 밖에서의 전투)
- ambush: 기습·매복·야습
- defense: 야전 방어 (진지 구축·후퇴 저지 등 성벽 밖 방어)
- siege_attack: 공성전 (도시·요새·성채 공격)
- siege_defense: 수성전 (도시·요새 안에서의 방어)
- diplomatic: 외교·협상·동맹·설득
- intrigue: 첩보·암살·모략·침투
- passive: 관찰·대기·이동·보고
- general: 위 어디에도 해당하지 않는 경우

JSON만 출력 (다른 텍스트 절대 금지):
{"type": "위 유형 중 하나", "location_name": "전투 발생 지명 또는 null", "target_faction_id": "대상 세력 id 또는 null"}"""


def _build_context(state: dict) -> str:
    lines: list[str] = []
    factions  = state.get("factions", {})
    locations = state.get("locations", {})

    if factions:
        lines.append("[세력]")
        for fid, f in factions.items():
            lines.append(f"  {fid}: {f.get('name', '')} [{f.get('disposition', '')}]")

    if locations:
        lines.append("[거점]")
        for loc in locations.values():
            name  = loc.get("name", "")
            short = name.split("(")[0].strip()
            ctrl  = loc.get("controller", "")
            ctrl_name = factions.get(ctrl, {}).get("name", ctrl) if ctrl else ""
            lines.append(f"  {short} (지배: {ctrl_name})")

    return "\n".join(lines)


def _keyword_fallback(command: str) -> dict:
    kw_type = classify_action_type(command)
    return {
        "type":              _KW_TO_CLS.get(kw_type, "general"),
        "location_name":     None,
        "target_faction_id": None,
        "_fallback":         True,
    }


async def classify_action_llm(command: str, state: dict) -> dict:
    """
    LLM으로 행동 유형을 분류합니다.

    반환 형태:
        {
            "type":              "open_field" | "ambush" | "defense" |
                                 "siege_attack" | "siege_defense" |
                                 "diplomatic" | "intrigue" | "passive" | "general",
            "location_name":     str | None,
            "target_faction_id": str | None,
            "_fallback":         bool  # True이면 LLM 실패로 키워드 폴백 사용됨
        }
    """
    context  = _build_context(state)
    user_msg = f"{context}\n\n[플레이어 명령]\n{command}"

    raw = await call_gemini_json([
        {"role": "system", "content": _SYSTEM},
        {"role": "user",   "content": user_msg},
    ])

    if raw is None:
        return _keyword_fallback(command)

    try:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1].lstrip("json").strip()
        data = json.loads(text)
        if data.get("type") in _ACTION_TYPES:
            data.setdefault("location_name",     None)
            data.setdefault("target_faction_id", None)
            data["_fallback"] = False
            return data
    except Exception:
        pass

    return _keyword_fallback(command)
