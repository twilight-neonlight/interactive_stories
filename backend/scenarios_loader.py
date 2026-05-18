"""
backend/scenarios_loader.py — 시나리오 데이터 로드 + 병력 규모 추정
"""

import json
import re
from pathlib import Path

SCENARIOS_DIR = Path(__file__).parent / "scenarios"

GARRISON_POINTS_BY_TIER: dict[str, int] = {
    "metropolis":    75,
    "major_city":    45,
    "regional_city": 25,
    "small_city":    12,
    "town":           5,
}

# 처분 유형별 garrison_modifier 초기값 (game.py의 _CONQUEST_DISPOSITIONS와 동기화)
_DISPOSITION_GARRISON_BASE: dict[str, float] = {
    "초토화":      0.1,
    "약탈":        0.2,
    "피해 최소화": 0.3,
}

_GARRISON_RECOVERY_PER_MONTH = 0.03

_EASTERN_KW = {
    "중국", "일본", "몽골", "오스만", "인도", "페르시아", "아랍", "한국", "조선", "청",
    "명", "당", "송", "무굴", "티무르", "오리엔트", "비잔틴", "사파비", "맘루크",
    "셀주크", "아나톨리아", "흑해", "실크로드",
}


def _estimate_troops_per_point(scenario: dict) -> int:
    """연도·동서양 맥락으로 strength_score 1점당 병력 수를 추정합니다."""
    eyebrow = scenario.get("eyebrow", "")
    m = re.search(r"(\d{3,4})년", eyebrow)
    year = int(m.group(1)) if m else 1200

    if   year < 500:   base = 20
    elif year < 1000:  base = 30
    elif year < 1300:  base = 45
    elif year < 1500:  base = 60
    elif year < 1700:  base = 85
    elif year < 1800:  base = 130
    elif year < 1900:  base = 220
    else:              base = 400

    # 동양 배경이면 1.3× (역사적으로 대규모 동원 경향)
    corpus = " ".join([
        eyebrow,
        scenario.get("title", ""),
        scenario.get("desc", ""),
        " ".join(scenario.get("tags", [])),
    ])
    if any(kw in corpus for kw in _EASTERN_KW):
        base = round(base * 1.3)

    return base


def _resolve_garrison(loc: dict, troops_per_point: int) -> int:
    """tier + garrison_modifier → garrison 병력수 계산. 명시적 garrison이 있으면 그대로 사용."""
    if "garrison" in loc:
        return int(loc["garrison"])
    tier = loc.get("tier")
    if not tier:
        return 0
    base_points = GARRISON_POINTS_BY_TIER.get(tier, 0)
    modifier    = loc.get("garrison_modifier", 1.0)
    return round(base_points * modifier * troops_per_point)


def load_scenarios() -> list[dict]:
    scenarios = []
    for scenario_dir in sorted(SCENARIOS_DIR.iterdir()):
        if not scenario_dir.is_dir():
            continue
        meta_path = scenario_dir / "meta.json"
        if not meta_path.exists():
            continue
        scenario = json.loads(meta_path.read_text(encoding="utf-8"))
        for key in ("locations", "factions", "characters", "events"):
            path = scenario_dir / f"{key}.json"
            scenario[key] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        if "troops_per_strength_point" not in scenario:
            scenario["troops_per_strength_point"] = _estimate_troops_per_point(scenario)
        tpp      = scenario["troops_per_strength_point"]
        start_ts = scenario.get("start_timestamp", "")
        for loc in scenario["locations"]:
            # conquered_at + conquest_disposition이 있으면 garrison_modifier를 자동 계산
            if ("garrison_modifier" not in loc
                    and "conquered_at" in loc
                    and "conquest_disposition" in loc
                    and start_ts):
                base = _DISPOSITION_GARRISON_BASE.get(loc["conquest_disposition"], 0.3)
                m1 = re.search(r'(\d{3,4})년\s*(\d{1,2})월', loc["conquered_at"])
                m2 = re.search(r'(\d{3,4})년\s*(\d{1,2})월', start_ts)
                if m1 and m2:
                    elapsed = (int(m2.group(1)) - int(m1.group(1))) * 12 + (int(m2.group(2)) - int(m1.group(2)))
                    loc["garrison_modifier"] = round(min(1.0, base + max(0, elapsed) * _GARRISON_RECOVERY_PER_MONTH), 4)
                else:
                    loc["garrison_modifier"] = base
            loc["garrison"] = _resolve_garrison(loc, tpp)
            if "controlling_faction" in loc and "controller" not in loc:
                loc["controller"] = loc.pop("controlling_faction")
        char_select_path = scenario_dir / "character-select.json"
        scenario["character_select"] = json.loads(char_select_path.read_text(encoding="utf-8")) if char_select_path.exists() else []
        # 시나리오 프롬프트 지시문 로드 (prompt.md + prompt_{char_id}.md)
        global_prompt_path = scenario_dir / "prompt.md"
        global_prompt = global_prompt_path.read_text(encoding="utf-8").strip() if global_prompt_path.exists() else ""
        char_prompts: dict[str, str] = {}
        for p in sorted(scenario_dir.glob("prompt_*.md")):
            char_id = p.stem[len("prompt_"):]
            char_prompts[char_id] = p.read_text(encoding="utf-8").strip()
        scenario["scenario_prompts"] = {"global": global_prompt, "characters": char_prompts}
        event_context_path = scenario_dir / "event_context.json"
        scenario["event_context"] = json.loads(event_context_path.read_text(encoding="utf-8")) if event_context_path.exists() else {}
        map_path = scenario_dir / "map.svg"
        scenario["map_svg"] = map_path.read_text(encoding="utf-8") if map_path.exists() else ""
        scenarios.append(scenario)
    return scenarios


SCENARIOS: list[dict] = load_scenarios()
