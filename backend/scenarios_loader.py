"""
backend/scenarios_loader.py — 시나리오 데이터 로드 + 병력 규모 추정
"""

import json
import re
from pathlib import Path

SCENARIOS_DIR = Path(__file__).parent / "scenarios"

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
        for key, filename in (("opening", "opening.json"), ("npc_pool", "npc-pool.json")):
            path = scenario_dir / filename
            scenario[key] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        map_path = scenario_dir / "map.svg"
        scenario["map_svg"] = map_path.read_text(encoding="utf-8") if map_path.exists() else ""
        if "troops_per_strength_point" not in scenario:
            scenario["troops_per_strength_point"] = _estimate_troops_per_point(scenario)
        scenarios.append(scenario)
    return scenarios


SCENARIOS: list[dict] = load_scenarios()
