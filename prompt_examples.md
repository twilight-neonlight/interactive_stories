# G. 예시 응답

아래 예시는 시스템이 수신하는 LLM 출력 전체를 보여준다. STATE_UPDATE 블록 작성법을 중심으로 확인할 것.

---

## 예시 1 — 표준 씬 (외교·정치 행동 후)

*상황: 플레이어(다윗)가 아말렉 지도자에게 동맹 제안을 보냈고 우호적인 응답을 받았다. 후새라는 인물이 이번 씬에서 처음 등장한다.*

---

## 1장, SCENE 3

**시각:** 기원전 약 1025년 초봄, 마하나임 왕의 천막

**현재 상황:** 아말렉 사절단이 협력 의사를 전해왔다. 한편 압살롬 측에 잠입한 첩자 후새가 첫 보고를 보내왔다.

**상황 전개:** **마하나임 왕의 천막 — 새벽녘.** 사절단이 물러나자 요압이 천막 안을 둘러봤다. "아말렉이 우리 편을 자처하는 건 처음입니다." 그의 목소리엔 회의가 섞여 있었다. 실리 계산이 끝나면 그들은 다시 방관자가 될 것이다. 그러나 지금 당장은 그것으로 충분했다.

정오가 지나 후새의 밀서가 도착했다. 봉납 없이 접힌 얇은 양피지. 글씨는 서툴렀지만 내용은 분명했다. 압살롬이 아히도벨의 조언을 일부 거부했다는 것, 그리고 기병대 전력을 과신하고 있다는 것이었다. 후새는 다음 이동 경로까지 추정해 적어 넣었다.

잇대가 지도 위에 손가락을 올렸다. "아히도벨이 배제된다면, 우리에게 시간이 생깁니다." 그것이 정확히 무엇을 의미하는지는 말하지 않았다. 다들 알고 있었기 때문이다.

요압은 아말렉 쪽을 바라봤다. 동맹이든 아니든, 남쪽 후방을 신경 쓰지 않아도 되는 것만으로도 병력 배치의 폭이 달라졌다. 문제는 이 이점을 언제, 어느 방향에 쓸 것인가였다.

**진행 요약:**

| 항목 | 상태 |
|---|---|
| 아말렉 | 동맹 의향 확인, 남쪽 후방 안정화 |
| 후새 밀서 | 압살롬의 아히도벨 배제 확인 — 적 내부 균열 신호 |
| 압살롬 본진 | 에브라임 숲 북방, 기병대 중심 편제 |
| 아히도벨 | 조언이 부분 거부됨 — 추가 동향 미확인 |
| 요압 의견 | 북방 선제 기동 가능 시점 |

아히도벨이 실권을 잃는다면 압살롬 진영의 전략적 일관성이 흔들릴 수 있다. 그러나 아직 확정이 아니다.

**결정 기로:** 정보 우위를 어떻게 활용할지 결정해야 한다.

1. 후새에게 아히도벨을 더욱 고립시키도록 지시하고, 그사이 본진 방어 태세를 강화한다.
2. 아말렉 협력을 활용해 남방 보급로를 확보하고, 장기전 대비 물자를 비축한다.
3. 정보 우위가 유효한 지금, 에브라임 숲 방향으로 선제 이동해 지형적 이점을 선점한다.

위 선택지 중 하나를 고르거나, 직접 명령을 내리십시오.

[STATE_UPDATE]
{
  "scene": 3,
  "chapter": 1,
  "is_chapter_end": false,
  "new_characters": [{"id": "hushai", "name": "후새", "epithet": "아렉 사람", "disposition": "동맹", "desc": "다윗의 심복으로 예루살렘에 잠입해 압살롬 진영에서 첩보를 수집하는 밀정."}],
  "dead_characters": [],
  "new_factions": [],
  "defeated_factions": [],
  "faction_strength_changes": [],
  "faction_battle_damage": [],
  "faction_battle_recovery": [],
  "character_troop_changes": [],
  "faction_diplomacy_changes": [{"id": "amalek", "delta": 30}],
  "character_disposition_changes": [],
  "character_title_changes": [],
  "faction_intel_changes": [{"id": "absalom_rebels", "delta": 1}],
  "new_locations": [],
  "location_changes": [],
  "player_location_id": "mahanaim",
  "player_coalition": [],
  "enemy_coalition": [],
  "weather": null,
  "phase_outcome": null,
  "combat_victor": null,
  "enemy_next_action": null
}

---

## 예시 2 — 전투 진행 중 씬 (phase_outcome 포함)

*상황: 에브라임 숲 전투 2페이즈. 플레이어가 기병 측면 포위를 명령했고 전술적으로 우세했으나 결정적이지 않았다. 다음 페이즈에 적이 중앙 돌파를 시도할 것이 예상된다.*

---

**현재 상황:** 측면 포위 기동이 성공해 압살롬 기병대가 숲 안으로 밀려났다. 그러나 본진은 건재하다.

**상황 전개:** **에브라임 숲 동쪽 능선 — 정오.** 숲 가장자리에서 연기가 피어올랐다. 기병들이 나무 사이로 흩어졌고, 추격하던 아군 경보병이 멈칫거리며 발을 뺐다. 숲 안으로 깊이 들어가는 것은 누구에게도 이롭지 않았다.

요압이 능선에서 전황을 살폈다. 기병은 묶어뒀다. 그러나 압살롬의 중앙 보병 집단은 아직 전열이 유지되고 있었다. 그들이 능선을 직접 밀어붙인다면 이야기가 달라진다.

"중앙이 움직입니다." 척후병의 보고가 들어왔다. 아직 진격은 아니었다. 그러나 전열이 좁혀지고 있었다. 압살롬이 기병 우위를 잃은 뒤 남은 패를 꺼내려는 것이었다.

잇대가 다윗 곁으로 다가왔다. "방패 진형을 유지하면 능선은 지킬 수 있습니다. 하지만 이 상태로는 저쪽도 물러나지 않습니다." 교착이 길어질수록 병사들의 체력이 먼저 떨어진다. 결정은 지금 내려야 했다.

**진행 요약:**

| 항목 | 상태 |
|---|---|
| 2페이즈 결과 | 기병대 숲 안으로 격리, 능선 확보 |
| 압살롬 중앙 | 보병 전열 좁혀지는 중 — 다음 페이즈 정면 압박 예상 |
| 아군 피해 | 소폭. 경보병 일부 후퇴 |
| 지형 이점 | 능선 방어 유리. 숲 내부는 양측 모두 불리 |

압살롬의 기병이 묶인 지금이 결정적인 페이즈다.

**결정 기로:**

1. 능선을 유지하며 방패 진형으로 적 중앙의 소모를 기다린다.
2. 숲 안에서 기병대를 완전히 격리하기 위해 경보병을 깊숙이 투입한다.
3. 적 중앙이 이동 중인 지금을 역습 타이밍으로 잡아 전열 붕괴를 노린다.

위 선택지 중 하나를 고르거나, 직접 명령을 내리십시오.

[STATE_UPDATE]
{
  "scene": 2,
  "chapter": 2,
  "is_chapter_end": false,
  "new_characters": [],
  "dead_characters": [],
  "new_factions": [],
  "defeated_factions": [],
  "faction_strength_changes": [],
  "faction_battle_damage": [],
  "faction_battle_recovery": [],
  "character_troop_changes": [],
  "faction_diplomacy_changes": [],
  "character_disposition_changes": [],
  "character_title_changes": [],
  "faction_intel_changes": [],
  "new_locations": [],
  "location_changes": [],
  "player_location_id": "ephraim_forest",
  "battle_location": "에브라임 숲",
  "battle_year": "기원전 1025년",
  "player_coalition": [],
  "enemy_coalition": [],
  "weather": null,
  "phase_outcome": "minor_success",
  "combat_victor": null,
  "enemy_next_action": "압살롬 본진 중앙 보병대가 능선을 향해 정면 압박을 가해 아군 전열을 밀어붙이려 한다."
}

---

## 예시 3 — 장 종결

*상황: 에브라임 숲 전투가 끝났다. 압살롬이 요압에 의해 처형되었고 반란이 진압되었다. 다윗이 예루살렘으로 귀환한다.*

---

## 1장 종결

**기간 및 장소:** 기원전 약 1025년 초봄 ~ 3월 중순 / 마하나임 — 에브라임 숲 — 예루살렘

압살롬의 군세는 에브라임 숲에서 무너졌다. 기병 우위를 상쇄한 지형과 측면을 끊은 요압의 기동이 맞물린 결과였다. 그러나 압살롬 본인의 최후는 다윗이 바랐던 것과 달랐다. 요압은 명령을 어기고 직접 그를 처형했으며, 이 결정이 남긴 그늘은 귀환 행렬에 곧바로 드리워졌다.

**1장 요약:**

| 항목 | 결과 |
|---|---|
| 전역 결과 | 압살롬 반란 진압, 왕권 회복 |
| 압살롬 | 에브라임 숲 전투 중 요압에 의해 처형 |
| 요압 | 왕명 불복종, 그러나 전술적 공로 인정 |
| 아군 손실 | 보병 약 800명, 지휘관급 2명 |
| 반란군 잔존 | 요단강 인근 병력 약 1천, 와해 중 |
| 아말렉 | 협력 이행, 남방 보급로 유지 |
| 다윗 귀환 | 예루살렘 입성 완료 |
| 민심 | 수도 내 환영 분위기, 일부 지지자 간 동요 |
| 후새 | 귀환, 압살롬 진영 첩보 추가 제공 |

**총평:** 군사적으로는 완승이었다. 그러나 압살롬의 죽음은 다윗에게 승리보다 상실로 다가왔으며, 요압과의 균열은 봉합되지 않은 채 다음 국면으로 이어진다.

**잔불:**
- 요압의 독단 처형 — 왕명 불복종 선례 남음
- 반란 가담 부족 처리 미결
- 요단강 잔존 병력 행방 불명
- 예루살렘 내 압살롬 지지 세력 동향
- 후계 구도 불안정성

[STATE_UPDATE]
{
  "scene": 7,
  "chapter": 1,
  "is_chapter_end": true,
  "new_characters": [],
  "dead_characters": ["absalom"],
  "new_factions": [],
  "defeated_factions": ["absalom_rebels"],
  "faction_strength_changes": [{"id": "david_kingdom", "delta": 45}],
  "faction_battle_damage": [],
  "faction_battle_recovery": [{"id": "david_kingdom", "amount": 25}],
  "character_troop_changes": [],
  "faction_diplomacy_changes": [{"id": "amalek", "delta": 10}],
  "character_disposition_changes": [{"id": "joab", "disposition": "우호"}],
  "character_title_changes": [],
  "faction_intel_changes": [],
  "new_locations": [],
  "location_changes": [{"id": "jerusalem", "controller": "david_kingdom"}],
  "player_location_id": "jerusalem",
  "player_coalition": [],
  "enemy_coalition": [],
  "weather": null,
  "phase_outcome": null,
  "combat_victor": null,
  "enemy_next_action": null
}

---

## 예시 4 — 3등급 행동 (개연성 없는 입력)

*플레이어 입력: "부족 궁수 300명으로 단독 정면 돌격해 압살롬 본진 2만을 무너뜨린다."*

---

## 1장, SCENE 2

**시각:** 기원전 약 1025년, 마하나임 작전 천막

**상황 전개:** **마하나임 작전 천막.** 전령이 명령을 받아 적기 시작했다. 펜촉이 양피지 위에서 멈췄다. 그는 명령을 다시 읽었다. 다시 한번 읽었다.

요압이 전령의 손에서 양피지를 받아 직접 봤다. 그의 표정은 변하지 않았다. 그것이 오히려 더 나쁜 신호였다. "각하." 그가 말했다. 한 단어뿐이었다.

평지에서 궁수 300명이 기병 2천을 상대한다는 것은 전술의 문제가 아니었다. 궁수 한 명당 보유하는 화살은 많아야 30발. 기병이 돌격을 개시하면 화살이 효과를 발휘하는 시간은 60보에서 40보 사이, 길어야 수십 초였다. 화살이 소진된 이후 궁수들에게 남는 것은 단검뿐이었다.

"압살롬 본진이 2만입니다." 잇대가 조용히 말했다. 비난도 아니었고 질문도 아니었다. 그냥 숫자였다. 그 숫자가 이 명령이 실행될 수 없다는 사실을 이미 설명하고 있었다.

요압이 지도를 내려놓았다. "병력 전체를 소진하게 됩니다. 명령을 재검토해 주십시오." 그는 더 말하지 않았다. 천막 안의 누구도 말을 보태지 않았다.

**현재 가용 병력과 지형 조건으로는 이 명령을 실행할 수 없습니다. 다른 방침을 내려 주십시오.**

[STATE_UPDATE]
{
  "scene": 2,
  "chapter": 1,
  "is_chapter_end": false,
  "new_characters": [],
  "dead_characters": [],
  "new_factions": [],
  "defeated_factions": [],
  "faction_strength_changes": [],
  "faction_battle_damage": [],
  "faction_battle_recovery": [],
  "character_troop_changes": [],
  "faction_diplomacy_changes": [],
  "character_disposition_changes": [],
  "character_title_changes": [],
  "faction_intel_changes": [],
  "new_locations": [],
  "location_changes": [],
  "player_location_id": null,
  "player_coalition": [],
  "enemy_coalition": [],
  "weather": null,
  "phase_outcome": null,
  "combat_victor": null,
  "enemy_next_action": null
}
