"""
routers/quick_battle.py — 빠른 역사적 전투 모드
역사적 전투를 즉시 시작할 수 있는 독립 전투 모드.
"""

from fastapi import APIRouter, HTTPException

from config        import SYSTEM_PROMPT
from gemini_client import call_gemini
from engine.turn   import extract_state_update
from engine.resolver import (
    _calc_threshold, _calc_max_phases, combat_prep_prompt,
)

router = APIRouter()

# ── 전투 설정 ──────────────────────────────────────────────────────────────────

QUICK_BATTLES: dict[str, dict] = {
    "adrianople-378": {
        "id":    "adrianople-378",
        "title": "아드리아노플 전투",
        "year":  378,
        "desc":  "로마 황제 발렌스 대 서고트 연합군. 기병의 매복이 제국의 운명을 바꿨다.",
        "context": (
            "378년 8월, 트라키아 평원. 동로마 황제 발렌스는 서고트 반란군을 토벌하기 위해 "
            "정예 야전군 약 15,000명을 이끌고 아드리아노플 인근에 도착했다. "
            "서방 황제 그라티아누스의 지원을 기다리지 않고 단독 공세를 결정했으나, "
            "서고트군 기병 주력이 전차 방어진 배후에 매복 중이라는 정찰 보고는 묵살됐다."
        ),
        "opening_hint": (
            "로마 레기온이 서고트 전차 방어진을 향해 전열을 펼치는 순간, "
            "측면에서 대규모 기병 집단이 쏟아져 나오기 시작한다. "
            "발렌스 황제로서 이 위기에 어떻게 대응할 것인가?"
        ),
        "player": {
            "id": "eastern-rome", "name": "동로마 야전군", "color": "#7F77DD",
            "strength_score": 750, "field_army": 15000,
            "notes": "황제 발렌스 직접 지휘. 정예 레기온이지만 서방 증원 없이 단독 공세.",
        },
        "enemy": {
            "id": "visigoths", "name": "서고트 연합군", "color": "#C5932A",
            "strength_score": 1000, "field_army": 20000,
            "notes": "프리티게른 지휘. 전차 방어진 뒤에 대규모 기병 매복.",
        },
        "player_commander": "발렌스 황제",
        "player_title":     "동방 황제",
        "troops_per_point": 20,
    },
    "tours-poitiers-732": {
        "id":    "tours-poitiers-732",
        "title": "투르-푸아티에 전투",
        "year":  732,
        "desc":  "카를 마르텔의 중보병 방어진 대 우마이야 칼리파국 기병군단.",
        "context": (
            "732년 10월, 투르와 푸아티에 사이 구릉지대. 우마이야 칼리파국의 압드 알-라흐만이 "
            "이끄는 기병 중심 대군이 피레네를 넘어 갈리아 깊숙이 진격했다. "
            "프랑크 궁재 카를 마르텔은 중무장 보병을 언덕에 배치해 기병의 충격력을 무력화할 지형을 선택했다."
        ),
        "opening_hint": (
            "이슬람 기병대가 파도처럼 밀려온다. 프랑크 밀집 방진이 언덕 위에서 버티고 있지만, "
            "기병의 속도와 충격력은 보병 전열에 엄청난 압박을 가한다."
        ),
        "player": {
            "id": "franks", "name": "프랑크 왕국군", "color": "#5DBB8B",
            "strength_score": 833, "field_army": 25000,
            "notes": "카를 마르텔 지휘. 중무장 보병 전열. 지형 우위(언덕). 기병 전력 부재.",
        },
        "enemy": {
            "id": "umayyad-caliphate", "name": "우마이야 칼리파국군", "color": "#C5932A",
            "strength_score": 1333, "field_army": 40000,
            "notes": "압드 알-라흐만 지휘. 빠른 경기병 중심. 장거리 원정으로 피로 누적.",
        },
        "player_commander": "카를 마르텔",
        "player_title":     "프랑크 궁재",
        "troops_per_point": 30,
    },
    "edington-878": {
        "id":    "edington-878",
        "title": "에딩턴 전투",
        "year":  878,
        "desc":  "앨프레드 대왕의 반격. 잉글랜드의 마지막 앵글로색슨 왕이 바이킹에 맞서다.",
        "context": (
            "878년 5월, 윌트셔 에딩턴 평야. 구스럼의 바이킹 기습으로 간신히 탈출한 앨프레드 대왕은 "
            "서머싯 습지의 은신처에서 병력을 재집결했다. 7주간의 게릴라 작전 끝에 "
            "머시아와 웨식스 전사들을 규합한 앨프레드가 적극적 반격에 나섰다."
        ),
        "opening_hint": (
            "앨프레드의 군세가 에딩턴 평야에서 바이킹 대군과 조우했다. "
            "겨울을 넘긴 전사들의 사기는 높지만, 바이킹의 방패벽 전술은 여전히 위협적이다."
        ),
        "player": {
            "id": "west-saxons", "name": "웨식스 왕국", "color": "#5DBB8B",
            "strength_score": 100, "field_army": 3000,
            "notes": "앨프레드 대왕 직할군. 7주 재집결로 사기 고양. 밀집 방패벽 전술.",
        },
        "ally": [
            {
                "id": "mercia", "name": "머시아", "color": "#5DBB8B",
                "strength_score": 33, "field_army": 1000,
                "notes": "앨프레드의 호소에 응한 머시아 전사들.",
            },
        ],
        "enemy": {
            "id": "great-heathen-army", "name": "이교도 대군", "color": "#8B2020",
            "strength_score": 167, "field_army": 5000,
            "notes": "구스럼 지휘. 잉글랜드를 거의 정복한 역전의 바이킹 전사들.",
        },
        "player_commander": "앨프레드 대왕",
        "player_title":     "웨식스 왕",
        "troops_per_point": 30,
    },
    "las-navas-1212": {
        "id":    "las-navas-1212",
        "title": "라스 나바스 데 톨로사 전투",
        "year":  1212,
        "desc":  "레콩키스타의 분기점. 이베리아 기독교 연합군 대 알모아드 칼리파국.",
        "context": (
            "1212년 7월, 시에라 모레나 산맥 남쪽 라스 나바스 데 톨로사 평원. "
            "알모아드 칼리파 무함마드 알-나시르가 이베리아 반도 중부를 장악하고 "
            "기독교 왕국들에 군사 압박을 가중시켰다. 카스티야의 알폰소 8세는 "
            "아라곤·나바라 왕들과 연합하고 교황의 십자군 선포를 등에 업고 맞섰다. "
            "알모아드군은 정예 흑인 친위대가 쇠사슬로 연결된 방어진을 구축했다."
        ),
        "opening_hint": (
            "알모아드 방어진 중앙의 쇠사슬 방벽이 기사단의 돌진을 막고 있다. "
            "나바라 왕 산초 7세의 기병이 측면 우회를 시도하는 한편, "
            "알폰소는 중앙 돌파를 결정해야 하는 순간에 직면했다."
        ),
        "player": {
            "id": "castile", "name": "카스티야 왕국", "color": "#C5932A",
            "strength_score": 120, "field_army": 5400,
            "notes": "알폰소 8세 지휘. 중기병 중심. 연합군 총사령.",
        },
        "ally": [
            {
                "id": "aragon", "name": "아라곤 왕국", "color": "#C5932A",
                "strength_score": 90, "field_army": 4050,
                "notes": "페드로 2세 지휘. 우익 기동.",
            },
            {
                "id": "navarre", "name": "나바라 왕국", "color": "#C5932A",
                "strength_score": 57, "field_army": 2550,
                "notes": "산초 7세 지휘. 측면 우회 담당.",
            },
        ],
        "enemy": {
            "id": "almohad-caliphate", "name": "알모아드 칼리파국군", "color": "#8B2020",
            "strength_score": 667, "field_army": 30000,
            "notes": "무함마드 알-나시르 지휘. 정예 흑인 친위대가 쇠사슬로 연결된 중앙 방어진 구축. 수적 우위.",
        },
        "player_commander": "알폰소 8세",
        "player_title":     "카스티야 왕·연합군 총사령관",
        "troops_per_point": 45,
    },
    "nicopolis-1396": {
        "id":    "nicopolis-1396",
        "title": "니코폴리스 전투",
        "year":  1396,
        "desc":  "십자군의 마지막 대원정. 지기스문트 대 바야지트 1세.",
        "context": (
            "1396년 9월, 다뉴브강 남안 니코폴리스. 헝가리 왕 지기스문트가 주도한 십자군은 "
            "프랑스·부르고뉴 기사단 포함 약 15,000명이 집결했다. 오스만 술탄 바야지트 1세는 "
            "비잔틴 포위를 일시 중단하고 정예 예니체리와 기병대를 이끌고 북진했다."
        ),
        "opening_hint": (
            "성급한 부르고뉴 기사단이 선제돌격을 강행했다. 오스만 보병 전열은 돌파했으나 "
            "그 배후에는 바야지트의 정예 예니체리가 기다리고 있다."
        ),
        "player": {
            "id": "hungary", "name": "헝가리 왕국", "color": "#5DBB8B",
            "strength_score": 120, "field_army": 7200,
            "notes": "지기스문트 왕 지휘. 주력 보병·기병.",
        },
        "ally": [
            {
                "id": "burgundy", "name": "부르고뉴 공국", "color": "#5DBB8B",
                "strength_score": 80, "field_army": 4800,
                "notes": "장 드 느베르 지휘. 프랑스·부르고뉴 기사단. 선제돌격 성향.",
            },
            {
                "id": "french-knights", "name": "프랑스 기사단", "color": "#5DBB8B",
                "strength_score": 50, "field_army": 3000,
                "notes": "독립적으로 행동하는 경향. 지휘 통일성 약함.",
            },
        ],
        "enemy": {
            "id": "ottoman-empire", "name": "오스만 제국군", "color": "#C5932A",
            "strength_score": 333, "field_army": 20000,
            "notes": "바야지트 1세 지휘. 예니체리 정예보병과 시파히 기병. 세르비아 보조군 후방 대기.",
        },
        "player_commander": "지기스문트 왕",
        "player_title":     "헝가리 왕·십자군 총사령관",
        "troops_per_point": 60,
    },
    "saratoga-1777": {
        "id":    "saratoga-1777",
        "title": "새러토가 전투",
        "year":  1777,
        "desc":  "미국 독립전쟁의 전환점. 게이츠의 대륙군이 버고인의 영국군을 포위·격파.",
        "context": (
            "1777년 10월, 뉴욕 주 새러토가. 영국군 총사령관 버고인은 캐나다에서 남하하여 "
            "허드슨강 계곡을 통해 식민지 반란군을 분열시키려 했다. "
            "프리먼 농장과 배미스 하이츠의 두 차례 교전 끝에 보급이 끊긴 영국군은 "
            "대륙군에게 사방에서 압박을 받고 있다."
        ),
        "opening_hint": (
            "모건의 저격수들이 숲에서 영국군 장교를 노리고, 베네딕트 아놀드의 부대가 "
            "측면을 돌파하려 한다. 게이츠 장군으로서 어떻게 결전을 이끌 것인가?"
        ),
        "player": {
            "id": "continental-army", "name": "대륙군", "color": "#5DBB8B",
            "strength_score": 300, "field_army": 15000,
            "notes": "호레이쇼 게이츠 지휘. 모건의 저격수 부대와 아놀드의 돌격대. 요새화된 방어선.",
        },
        "enemy": {
            "id": "british-crown", "name": "영국 왕당파군", "color": "#C5932A",
            "strength_score": 120, "field_army": 6000,
            "notes": "버고인 지휘. 보급 고갈, 독일 용병 포함. 포위 위기에 처한 정규군.",
        },
        "player_commander": "호레이쇼 게이츠",
        "player_title":     "북부군 사령관",
        "troops_per_point": 50,
    },
    "austerlitz-1805": {
        "id":    "austerlitz-1805",
        "title": "아우스터리츠 전투",
        "year":  1805,
        "desc":  "나폴레옹의 최고 걸작. 수적 열세에도 러시아·오스트리아 연합군을 격파.",
        "context": (
            "1805년 12월, 모라비아 아우스터리츠 평원. 나폴레옹은 의도적으로 우익을 약화시켜 "
            "연합군의 좌익 우회를 유도했다. 연합군이 프라체 고지를 비우며 중앙이 "
            "취약해지는 순간, 프랑스군의 집중 돌파가 시작된다."
        ),
        "opening_hint": (
            "연합군이 프라체 고지를 향해 좌익 병력을 쏟아부으며 중앙이 열리고 있다. "
            "생-일레르와 반담의 사단이 돌파 준비를 마쳤다. 황제, 명령을 내릴 시간이다."
        ),
        "player": {
            "id": "french-empire", "name": "프랑스 제국군", "color": "#7F77DD",
            "strength_score": 365, "field_army": 73000,
            "notes": "나폴레옹 보나파르트 지휘. 대육군(그랑다르메). 병사들의 사기 최고조. 기동 집중력 탁월.",
        },
        "enemy": {
            "id": "austrian-empire", "name": "오스트리아 제국군", "color": "#8B2020",
            "strength_score": 190, "field_army": 38000,
            "notes": "프란츠 2세 명목 지휘. 좌익 우회 기동을 주도.",
        },
        "enemy_ally": [
            {
                "id": "russian-empire", "name": "러시아 제국군", "color": "#8B2020",
                "strength_score": 235, "field_army": 47000,
                "notes": "알렉산드르 1세·쿠투조프 지휘. 프라체 고지 방면 좌익 공세 주도.",
            },
        ],
        "player_commander": "나폴레옹 보나파르트",
        "player_title":     "프랑스 황제",
        "troops_per_point": 200,
    },
    "kursk-1943": {
        "id":    "kursk-1943",
        "title": "쿠르스크 전투",
        "year":  1943,
        "desc":  "역사상 최대의 기갑전. 소련군의 종심 방어가 독일군 치타델 작전을 분쇄.",
        "context": (
            "1943년 7월, 쿠르스크 돌출부. 독일군 치타델 작전은 소련 돌출부를 남북에서 "
            "협공해 대규모 포위를 노렸다. 그러나 소련 정보망이 계획을 사전에 입수했고, "
            "주코프와 바실렙스키는 8개 방어선을 구축해 독일 기갑부대를 소모시킨 뒤 "
            "반격으로 전환하는 전략을 세웠다."
        ),
        "opening_hint": (
            "독일 기갑 집단이 방어선을 뚫으며 밀려오고 있다. "
            "종심 방어선이 충격을 흡수하는 동안, 프로호로프카에서 반격의 시점을 결정해야 한다."
        ),
        "player": {
            "id": "soviet-red-army", "name": "붉은 군대", "color": "#8B2020",
            "strength_score": 900, "field_army": 900000,
            "notes": "주코프·바실렙스키 지휘. 8개 종심 방어선 구축. 전차·대전차포 집중 배치. 반격 예비대 대기.",
        },
        "enemy": {
            "id": "nazi-germany", "name": "독일 국방군", "color": "#C5932A",
            "strength_score": 700, "field_army": 700000,
            "notes": "만슈타인·클루게 지휘. 티거·판터 신형 전차 집중 투입. 치타델 작전.",
        },
        "player_commander": "게오르기 주코프",
        "player_title":     "소련군 총참모장",
        "troops_per_point": 1000,
    },
}


@router.get("/api/quick-battles")
def list_quick_battles():
    """전투 목록 반환 (카드 렌더링용)."""
    result = []
    for b in QUICK_BATTLES.values():
        p, e = b["player"], b["enemy"]
        player_names = [p["name"]] + [a["name"] for a in b.get("ally", [])]
        enemy_names  = [e["name"]] + [a["name"] for a in b.get("enemy_ally", [])]
        result.append({
            "id":    b["id"],
            "title": b["title"],
            "year":  b["year"],
            "desc":  b["desc"],
            "player_name":  " / ".join(player_names),
            "enemy_name":   " / ".join(enemy_names),
            "player_color": p["color"],
            "enemy_color":  e["color"],
        })
    return result


@router.post("/api/quick-battle/{battle_id}/start")
async def start_quick_battle(battle_id: str):
    """전투 초기 상태 + LLM 개시 장면 반환."""
    battle = QUICK_BATTLES.get(battle_id)
    if not battle:
        raise HTTPException(status_code=404, detail=f"알 수 없는 전투 ID: {battle_id}")

    p = battle["player"]
    e = battle["enemy"]
    allies       = battle.get("ally", [])
    enemy_allies = battle.get("enemy_ally", [])

    # ── 연합 전력 합산 후 초기 사기 계산
    total_p_str = p["strength_score"] + sum(a["strength_score"] for a in allies)
    total_e_str = e["strength_score"] + sum(a["strength_score"] for a in enemy_allies)

    p_mom = _calc_threshold(total_p_str, total_e_str, 0, 0)
    e_mom = _calc_threshold(total_e_str, total_p_str, 0, 0)
    max_phases = _calc_max_phases(total_p_str + total_e_str)

    combat_state = {
        "active":                True,
        "phase_number":          1,
        "max_phases":            max_phases,
        "player_faction_id":     p["id"],
        "enemy_faction_id":      e["id"],
        "player_morale":       p_mom,
        "player_morale_max":   p_mom,
        "enemy_morale":        e_mom,
        "enemy_morale_max":    e_mom,
        "prep_tier_en":          "partial",
        "pending_battle_damage": {p["id"]: 0, e["id"]: 0},
        "phase_results":         [],
    }
    if allies:
        combat_state["player_coalition"] = [p["name"]] + [a["name"] for a in allies]
    if enemy_allies:
        combat_state["enemy_coalition"] = [e["name"]] + [a["name"] for a in enemy_allies]

    # ── 팩션 딕셔너리 구성
    factions_dict: dict = {}
    for f in [p] + allies:
        factions_dict[f["id"]] = {**f, "disposition": "우호",  "battle_damage": 0, "diplomacy_score":  80, "intel_level": 4}
    for f in [e] + enemy_allies:
        factions_dict[f["id"]] = {**f, "disposition": "적대",  "battle_damage": 0, "diplomacy_score": -80, "intel_level": 2}

    total_p_army = p["field_army"] + sum(a["field_army"] for a in allies)

    commander_id = "player-commander"
    state_json = {
        "scenarioId":    "quick-battle",
        "scenarioTitle": battle["title"],
        "protagonist":   commander_id,
        "progress": {
            "chapter":      1,
            "scene":        1,
            "chapterTitle": battle["title"],
            "timestamp":    f"{battle['year']}년",
            "isChapterEnd": False,
        },
        "history":    [],
        "characters": {
            commander_id: {
                "id":          commander_id,
                "name":        battle["player_commander"],
                "title":       battle["player_title"],
                "status":      "alive",
                "faction_id":  p["id"],
                "disposition": "우호",
                "troops_count": total_p_army,
            },
        },
        "factions":    factions_dict,
        "locations":   {},
        "events":      [],
        "combatState": combat_state,
    }

    resolution = {
        "tier": "부분 성공", "tier_en": "partial",
        "roll": None, "net": None,
        "action_type": "military", "modifiers": [],
    }

    # ── LLM 호출: 전투 개시 장면 생성
    ally_lines       = "".join(f"아군 동맹 — {a['name']}: {a['notes']}\n" for a in allies)
    enemy_ally_lines = "".join(f"적군 동맹 — {a['name']}: {a['notes']}\n" for a in enemy_allies)
    hist_block = (
        f"\n\n## 역사적 전투 설정\n"
        f"전투명: {battle['title']} ({battle['year']}년)\n"
        f"아군 — {p['name']}: {p['notes']}\n"
        f"{ally_lines}"
        f"적군 — {e['name']}: {e['notes']}\n"
        f"{enemy_ally_lines}"
        f"배경: {battle['context']}\n"
    )
    cs_prompt = combat_prep_prompt(combat_state, resolution).replace(
        "전투 준비 결과: **부분 성공**\n",
        f"역사적 배경 전투 (준비 단계 생략)\n",
    ).replace(
        "이 결과에 따라 전투 개시 장면을 서술하시오.",
        "위 역사적 상황에 맞는 전투 개시 장면을 서술하시오.",
    )

    content = await call_gemini([
        {"role": "system", "content": SYSTEM_PROMPT + hist_block + cs_prompt},
        {"role": "user",   "content": f"[역사적 전투 개시: {battle['title']}] {battle['opening_hint']}"},
    ])
    content, _ = extract_state_update(content)

    return {
        "title":           battle["title"],
        "year":            battle["year"],
        "content":         content,
        "state_json":      state_json,
        "resolution":      resolution,
        "troops_per_point": battle["troops_per_point"],
    }
