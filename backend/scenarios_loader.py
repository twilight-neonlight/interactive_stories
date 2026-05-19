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

# 이 유형은 거점 tier 기여분 없이 field_army만으로 strength_score 계산
_NO_TERRITORY_TYPES: frozenset[str] = frozenset({"rebels", "remnant"})


def compute_faction_strength(faction: dict, fid: str, locations: list, tpp: int) -> int:
    """field_army·보유 거점·naval_base에서 strength_score를 계산합니다.

    Args:
        faction:   세력 데이터 dict (field_army, type, naval_base 포함 가능)
        fid:       세력 id (controller 매핑에 사용)
        locations: list[dict] 형태의 거점 목록 (dict of {lid: loc} 도 허용)
        tpp:       troops_per_strength_point
    """
    if not tpp:
        return faction.get("strength_score", 0)
    ftype = faction.get("type", "")
    base  = round((faction.get("field_army") or 0) / tpp)

    if ftype not in _NO_TERRITORY_TYPES:
        loc_iter = locations.values() if isinstance(locations, dict) else locations
        tier_pts = sum(
            GARRISON_POINTS_BY_TIER.get(loc.get("tier", ""), 0)
            for loc in loc_iter
            if loc.get("controller") == fid
        )
        if ftype == "republic":
            tier_pts *= 2  # 용병 고용 — 자국 도시 방위군 2배
        base += tier_pts

    # naval_base: republic 전용 아님 — 해군력이 있는 모든 세력 유형에 적용 가능
    base += faction.get("naval_base", 0)

    return max(1, base)

# 처분 유형별 garrison_modifier 초기값 (game.py의 _CONQUEST_DISPOSITIONS와 동기화)
_DISPOSITION_GARRISON_BASE: dict[str, float] = {
    "초토화":      0.1,
    "약탈":        0.2,
    "피해 최소화": 0.3,
}

_GARRISON_RECOVERY_PER_MONTH = 0.03

# 동유럽·중동·이슬람 문명권 → base × 1.5
_MIDEAST_EEUROPE_KW = {
    # 중동·이슬람
    "오스만", "비잔틴", "아랍", "페르시아", "사파비", "맘루크",
    "셀주크", "아나톨리아", "오리엔트", "실크로드", "흑해", "티무르",
    "이슬람", "칼리파", "술탄국",
    # 동유럽·슬라브·발칸
    "러시아", "폴란드", "슬라브", "헝가리", "발칸", "프로이센",
    "코사크", "리투아니아", "오스트리아",
}

# 아시아(특히 동아시아)·남아시아·중앙아시아 → base × 3.0
_EAST_ASIA_KW = {
    "중국", "일본", "몽골", "한국", "조선", "청", "명", "당", "송", "원",
    "고려", "신라", "고구려", "발해", "무굴", "인도",
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

    corpus = " ".join([
        eyebrow,
        scenario.get("title", ""),
        scenario.get("desc", ""),
        " ".join(scenario.get("tags", [])),
    ])
    if any(kw in corpus for kw in _EAST_ASIA_KW):
        base = round(base * 2.5)
    elif any(kw in corpus for kw in _MIDEAST_EEUROPE_KW):
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
        scenario = json.loads(meta_path.read_text(encoding="utf-8-sig"))
        for key in ("locations", "factions", "characters", "events"):
            path = scenario_dir / f"{key}.json"
            scenario[key] = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else []
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
        # strength_score를 field_army + 거점 + naval_base에서 재계산
        for f in scenario["factions"]:
            f["strength_score"] = compute_faction_strength(f, f["id"], scenario["locations"], tpp)
        char_select_path = scenario_dir / "character-select.json"
        scenario["character_select"] = json.loads(char_select_path.read_text(encoding="utf-8-sig")) if char_select_path.exists() else []
        # 시나리오 프롬프트 지시문 로드 (prompt.md + prompt_{char_id}.md)
        global_prompt_path = scenario_dir / "prompt.md"
        global_prompt = global_prompt_path.read_text(encoding="utf-8-sig").strip() if global_prompt_path.exists() else ""
        char_prompts: dict[str, str] = {}
        for p in sorted(scenario_dir.glob("prompt_*.md")):
            char_id = p.stem[len("prompt_"):]
            char_prompts[char_id] = p.read_text(encoding="utf-8-sig").strip()
        scenario["scenario_prompts"] = {"global": global_prompt, "characters": char_prompts}
        event_context_path = scenario_dir / "event_context.json"
        scenario["event_context"] = json.loads(event_context_path.read_text(encoding="utf-8-sig")) if event_context_path.exists() else {}
        map_path = scenario_dir / "map.svg"
        scenario["map_svg"] = map_path.read_text(encoding="utf-8-sig") if map_path.exists() else ""
        scenarios.append(scenario)
    return scenarios


SCENARIOS: list[dict] = load_scenarios()
