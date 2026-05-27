# Interactive Stories

**역사·창작 세계를 배경으로 한 AI 기반 인터랙티브 전쟁·정치 시뮬레이션 게임**

플레이어의 선택이 세계를 바꾼다. 역사의 분기점에 서서 군사·외교·내정 판단을 내리고, AI가 그 결과를 세계에 반영한다.

---

## 기능 개요

### 시나리오 시스템
- 프리셋 시나리오 중심으로 지원
- 커스텀 시나리오 입력 기능은 아직 미구현 (선택 시 안내 토스트 표시)
- 시나리오마다 고유한 배경 SVG 지도, 세력 배치, 등장 인물 설정 보유
- 주인공 선택형(`protagonistMode: select`) / 고정형(`fixed`) 분기 지원
- 시나리오 데이터(`backend/scenarios/{id}/`)는 JSON 파일로 분리 관리 — 코드 수정 없이 편집 가능
- 선택형 시나리오는 `character-select.json`에서 선택 카드 데이터를 관리하고, `characters.json`의 인물 원본 데이터와 조합해 표시

### AI 내러티브 엔진 (TurnEngine)
- Google Gemini(`gemini-3.1-flash-lite`)를 내러티브 생성 모델로 사용
- 플레이어 입력 → 백엔드 `/api/turn` → AI 응답 → 상태 갱신의 단방향 흐름
- 선택지는 LLM이 `[attack]`, `[siege]`, `[diplomatic]`, `[intrigue]` 같은 행동 태그를 붙이고, 백엔드는 이 태그와 LLM 행동 분류기(`classifier.py`)를 함께 사용해 판정 유형을 결정
- 행동 판정 5단계: **대성공 / 성공 / 부분 성공 / 실패 / 대실패**
- 일반 행동 판정은 **4d6 + 보정치**로 결정하며, 아래 두 보정치가 합산됨:
  - **LLM 품질 평가** (최대 ±2): 체스 기보 기호(!!·!·=·?·??)로 전략적 선택 품질을 평가
  - **능력치 등급차** (최대 ±5): 플레이어와 상대 지휘관의 해당 능력치 등급 차이 → 행동 유형별 적용 능력치:

    | 행동 유형 | 적용 능력치 |
    |-----------|------------|
    | 군사·방어 | 통솔 |
    | 기습·첩보·모략 | 지략 |
    | 외교      | 외교 |

- 전투 페이즈 판정은 전장 지형·날씨·성벽(tier 기반) 보정을 추가 반영
- 수동적 관찰·대기 등은 별도 주사위 판정 없이 서술형으로 처리
- LLM 응답의 `**시각:**` 줄과 `[STATE_UPDATE]` JSON 블록을 파싱해 시각·상태 변화를 갱신

### 다중 페이즈 전투 시스템
- 야전·기습·공성 행동은 즉시 단일 결과로 끝나지 않고 전투 오버레이(`combat-ui.js`)로 진입
- 전투 시작 시 `combatState`를 생성해 양측 전력, 사기, 페이즈 번호, 적 예고 행동, 누적 피해를 추적
- 각 페이즈는 **아군 2d6 vs 적군 2d6** 대결로 처리되며, 주사위 차이에 지형·날씨·성벽(tier 기반)·품질 수정치를 더해 7단계 `phase_outcome`을 엔진이 직접 결정함 (LLM은 phase_outcome을 출력하지 않음)
- 결정된 `phase_outcome`은 다음 턴 시작 시 사기와 전투 피해에 적용됨
- 전투 개시 응답에서 LLM이 `battle_location`, `battle_year`, `battle_terrain`을 구조화 출력하며, `weather`가 없으면 지형별 가중치로 날씨를 자동 롤
- 사기(`player_morale` / `enemy_morale`)는 0–100 범위이며, 전투 오버레이 상단 막대에 현재 전황 지표로 표시
- 오버레이는 양측 지휘관 카드, 병력 추정치, 전장 지형·날씨 배지, 교전 기록을 함께 표시
- `combat_victor`는 최소 교전 페이즈 이후에만 수용하며, 플레이어는 언제든 후퇴를 선택할 수 있음
- 전투 종료 시 누적 `pending_battle_damage`가 `faction_battle_damage`로 확정되어 세력 전력과 병력 수에 반영

### 다중 라운드 외교 회담 (개발 중)
- 고위급 회담·특사 접견·공식 협상은 단일 외교 판정이 아니라 외교 오버레이(`diplomacy-ui.js`)로 진입 예정
- `diplomacyState`가 회담 대상 세력, 라운드 번호, 상대의 다음 태도, 라운드 기록을 추적
- 각 라운드는 4d6 외교 판정 + 품질·능력치·외교 관계 보정을 반영
- LLM은 회담 진행 중 `opponent_next_stance`와 필요 시 `diplomacy_outcome`(`agreement` / `breakdown`)을 출력
- 플레이어는 회담 도중 언제든 **회담 중단**을 선택할 수 있음
- **현재 상태**: 외교 오버레이 UI가 미완성이므로 외교 턴도 일반 씬으로 처리됨. 전용 오버레이는 추후 활성화 예정

### 빠른 역사적 전투
- 메인 메뉴의 **빠른 역사적 전투**에서 사전 정의된 역사 전투를 바로 시작 가능
- `/api/quick-battles`로 전투 목록을 조회하고 `/api/quick-battle/{battle_id}/start`로 독립 전투 상태를 생성
- 빠른 전투는 별도 시나리오 진행 없이 `quick-battle` 상태를 세션에 저장해 전투 오버레이로 바로 진입
- 전투 종료 후 **다시 하기** 또는 **메인 화면으로** 돌아가기 지원

### 상태 관리 (GameState / StateManager)

**인물 (`characters`)**
- 상태: `alive` / `dead` / `unknown` / `exiled`
- `troops_count`: 직접 지휘 병력 수 (delta 누적으로 변경)
- `disposition`: 플레이어에 대한 성향 (동적 변경 가능)
- `stats`: 5개 능력치 등급 객체. 주요 인물은 시나리오에서 직접 지정하며, 게임 중 동적으로 추가된 NPC는 정규분포로 자동 배정됨.

  | 능력치 | 적용 대상 |
  |--------|-----------|
  | 통솔 | 군사·공성·방어 행동 판정 수정치 |
  | 지략 | 기습·첩보 행동 판정 수정치 |
  | 외교 | 외교 행동 판정 수정치 |
  | 행정 | 예비 인력·주둔군 회복률 보정 |
  | 무력 | (UI 표시용) |

  등급 범위: `F` ~ `S` (17단계, F / E-~E+ / D-~D+ / C-~C+ / B-~B+ / A-~A+ / S)

- 게임 중 동적 추가된 인물에는 `is_dynamic: true` 플래그

**세력 강도와 병력 (`factions` — strength / field_army / reserve)**

세력 강도는 현재 버전에서 시나리오 로드·턴 처리 시 자동 재계산됩니다:

| 속성 | 설명 |
|---|---|
| `field_army` | 즉시 전장에 투입 가능한 상비군 수 |
| `reserve_manpower` | 예비 인력. 시간 경과와 행정 능력에 따라 회복 |
| `strength_score` | 상비군·예비 인력·보유 거점 tier·해군 기반을 합산한 기반 점수 |
| `battle_damage` | 전투 피해로 누적되는 임시 페널티. 시간 경과로 회복 |

실효 강도 = `strength_score − battle_damage`

`meta.json`에 `troops_per_strength_point` 값을 설정하면 강도 점수를 추정 병력 수로 변환해 UI와 LLM 컨텍스트에 표시합니다. 미설정 시 시나리오의 연도·동서양 배경에서 자동 추정합니다.

`reserve_tpp_divisor`는 예비 인력이 strength_score로 환산되는 효율을 결정합니다. 미설정 시 연도 기반으로 자동 추정합니다.

**세력 재정 (`factions` — fiscal)**

재정은 플레이어 세력 기준으로 자동 계산되어 LLM 컨텍스트와 회복 속도에 반영됩니다.

| 속성 | 설명 |
|---|---|
| `income_mult` / `income_flat` | 거점 tier 기반 월수입에 곱하거나 더하는 세력별 수입 보정 |
| `treasury` | 누적 비축금. 월간 수지와 `treasury_changes`로 자동 갱신 |
| `fiscal_level` | 월수입 대비 수지로 산출되는 재정 상태(풍요/안정/균형/적자/파산) |

- 월수입은 보유 거점 tier와 주둔 안정도(`garrison_modifier`)를 기반으로 계산
- 월지출은 상비군과 동원 가능한 예비 인력을 기반으로 계산
- 재정 상태는 예비 인력 회복과 점령지 주둔군 회복 속도에 배율로 반영
- `faction_income_changes`와 `treasury_changes`는 LLM이 출력할 수 있고, 자연 월간 수지는 시스템이 자동 누적

**세력 외교 (`factions` — diplomacy)**

| 속성 | 범위 | 설명 |
|---|---|---|
| `diplomacy_score` | −100 – +100 | 플레이어에 대한 우호도 수치 |
| `disposition` | 동맹 / 우호 / 중립 / 비우호 / 적대 | 수치에서 자동 산출 |

수치 → 태도 변환 기준:

- `>= 67` → **동맹**
- `34 ~ 66` → **우호**
- `−33 ~ 33` → **중립**
- `−66 ~ −34` → **비우호**
- `< −66` → **적대**

`faction_diplomacy_changes`로 delta 누적 시 태도 자동 재계산. `faction_disposition_changes`로 태도를 직접 설정하면 점수도 해당 초기값으로 보정됩니다.

**거점 (`locations`)**
- `controller`: 현재 지배 세력 id
- 게임 중 점거·해방 시 `location_changes`로 갱신

**전투 상태 (`combatState`)**
- `active`: 전투 진행 여부
- `player_faction_id` / `enemy_faction_id`: 전투 양측 세력 id
- `player_strength` / `enemy_strength`: 전투 시작 시점의 실효 전력
- `player_morale` / `enemy_morale`: 전투 사기(0–100), 오버레이의 주 전황 지표
- `phase_number`: 다음 페이즈 번호
- `battle_location_name` / `battle_year` / `battle_terrain`: 전투 표시명·연도·전장 지형
- `player_coalition` / `enemy_coalition`: 전장에 실제 등장한 연합 세력 표시명 목록
- `enemy_next_action`: 다음 페이즈 적 예고 행동
- `pending_phase_outcome`: 직전 장면의 결과. 다음 페이즈 시작 시 사기·피해로 적용
- `pending_battle_damage`: 전투 중 누적 피해. 전투 종료 시 `faction_battle_damage`로 확정
- `is_siege`, `siege_location_id`, `siege_garrison`: 공성전 전용 정보

**외교 회담 상태 (`diplomacyState`)**
- `active`: 회담 진행 여부
- `player_faction_id` / `target_faction_id`: 회담 양측 세력 id
- `session_label`: 회담 표시명
- `round_number`: 다음 라운드 번호
- `opponent_next_stance`: 다음 라운드 상대 태도·요구
- `round_results`: 라운드별 판정 기록
- `ended` / `outcome`: 회담 종료 여부와 결과(`agreement` / `breakdown`)

**대화 히스토리**
- 전체 턴 히스토리를 `{role, content}[]` 형태로 유지해 맥락 연속성 보장
- 진행 중인 게임 상태는 `sessionStorage`에 직렬화(JSON)되어 새로고침·동일 탭 세션에서 복원
- 사용자가 저장 버튼을 누르면 `/api/saves`를 통해 사용자별 서버 저장소(`saves/{user_id}/`)에 JSON 세이브 파일 생성

### 상태 자동 업데이트 (STATE_UPDATE 블록)
LLM이 씬 응답 끝에 `[STATE_UPDATE] { ... }` 형식의 구조화된 블록을 포함하면, 백엔드가 이를 파싱해 프론트엔드에 전달합니다:

| 키 | 설명 |
|---|---|
| `new_characters` / `dead_characters` | 인물 등장·사망 |
| `new_factions` / `defeated_factions` | 새 세력 추가 / 세력 패퇴(지도자 사망·전 거점 상실 시) |
| `faction_field_army_changes` | 세력 상비군 변화(delta, 명 단위) |
| `faction_reserve_changes` | 세력 예비 인력 변화(delta, 명 단위). 자연 회복은 시스템 자동 처리 |
| `faction_strength_overrides` | 상비군·예비 인력·거점 변화 반영 후 재계산된 strength_score |
| `faction_battle_damage` / `faction_battle_recovery` | 전투 피해 누적·회복 (임시적) |
| `faction_diplomacy_changes` | 외교 수치 변경 (delta → 태도 자동 재계산) |
| `faction_disposition_changes` | 외교 태도 직접 설정 |
| `faction_intel_changes` | 세력 첩보 수준 변경 (0–4 범위로 clamp) |
| `faction_income_changes` | 세력 수입 배율·고정 수입 변경 |
| `treasury_changes` / `treasury_update` | 일회성 재정 변화 / 시스템이 계산한 최종 비축금 |
| `character_troop_changes` | 인물 병력 변경 (delta) |
| `character_disposition_changes` | 인물 성향 변경 |
| `character_title_changes` | 인물 직위·칭호 변경 (즉위·승진·폐위 등) |
| `new_locations` / `location_changes` | 거점 추가·지배 세력 변경 |
| `player_location_id` | 플레이어의 현재 거점 id (사이드바 위치 표시에 사용) |
| `weather` | 현재 날씨 설정. 전투 페이즈의 날씨 보정과 UI 배지에 사용 |
| `battle_location` / `battle_year` / `battle_terrain` | 전투 개시 응답에서 전장 표시 정보와 전장 지형을 지정 |
| `diplomacy_outcome` / `opponent_next_stance` | 외교 회담 진행 중 결론·다음 라운드 상대 태도 지정 |
| `combat_state` | 전투 시작·진행·종결 상태 갱신 |
| `diplomacy_state` | 외교 회담 시작·진행·종결 상태 갱신 |

전투 진행 중에는 일반 `faction_battle_damage`를 즉시 수용하지 않고, 엔진이 `phase_outcome`과 `pending_battle_damage`를 통해 피해를 관리합니다. LLM은 `phase_outcome`을 출력하지 않으며, 전투 관련 LLM 출력에는 `combat_victor`, `enemy_next_action`, `player_coalition`, `enemy_coalition`, `battle_terrain` 등이 사용됩니다.

### 지도 시스템
- SVG 지도 파일(`map.svg`)을 시나리오 폴더에 배치하면 인라인으로 자동 삽입됨
- 거점 좌표는 SVG 크기 대비 퍼센트(`0–100`)로 저장 → 해상도·비율 변화에 무관하게 정확히 위치
- CSS 절대 위치 마커 + 펄스 애니메이션으로 렌더링
- 마커 색상: 본국 영토(초록) / 동맹 거점(파랑) / 적 점거(빨강) / 불안정(주황) / 중립(회색) — 시나리오별 커스터마이즈 가능
- `tools/map-coord-picker.html`을 브라우저에서 열어 이미지를 불러온 뒤 클릭하면 좌표를 바로 기록·복사 가능

### 게임 UI (3열 레이아웃)
| 영역 | 내용 |
|---|---|
| 좌측 | 지휘관 프로필(1) · 주요 인물 목록(2) · 세력 현황 바(2) — flex 비율 1:2:2 |
| 중앙 | 씬 본문(마크다운 렌더링), 판정 배지, 시각·장소 표시 |
| 우측 | 배경 지도(SVG + CSS 마커), 동시 진행 사건, 선택지 버튼 + 자유 입력창 |

- 지휘관 프로필: 직위·병력(추정 수치 범위)·거점·**능력치 등급**(통솔/지략/외교/행정/무력)을 표시
- 지도 마커·세력 현황 바 툴팁에 세력 고유 색상 도트 표시
- 인물·지도 마커·사건 항목에 **호버 툴팁** 제공 (세부 정보 표시)
- 전투 발생 시 전용 오버레이로 전환해 사기 막대, 지휘관 카드, 병력 추정, 교전 기록, 판정 배지, 후퇴 버튼, 전술 명령 입력창 표시
- 고위급 외교 회담 발생 시 외교 오버레이로 전환 예정 (현재는 일반 씬으로 처리)
- 판정 배지는 일반 행동 등급 또는 전투 페이즈 결과를 표시하며, 툴팁에서 주사위 결과(일반: 4d6, 전투: 아군 2d6 vs 적군 2d6)와 보정 정보를 확인 가능
- URL에 `?debug` 파라미터를 추가하면 판정·STATE_UPDATE·적 예고 행동 디버그 패널을 씬 하단에 표시
- `frontend/combat-debug.html`에서 전투 UI와 페이즈 결과를 서버 호출 없이 점검 가능

---

## 기술 스택

| 구분 | 사용 기술 |
|---|---|
| 프론트엔드 | Vanilla HTML / CSS / JavaScript |
| 백엔드 | Python, FastAPI, Uvicorn |
| AI 모델 | Google Gemini (`gemini-3.1-flash-lite`) |
| 인증 | JWT (python-jose) — 게스트 UUID / Google OAuth 2.0 |
| 상태 저장 | sessionStorage (진행 중 게임 상태) / 서버 JSON 세이브 / localStorage + 쿠키 (인증 토큰·게스트 UUID) |
| 패키지 관리 | pip / venv |
| 배포 | Oracle Cloud (Ubuntu 22.04), nginx, systemd, Let's Encrypt (HTTPS) |

---

## 프로젝트 구조

```
interactive_stories/
├── backend/
│   ├── main.py                     # FastAPI 앱 팩토리 (미들웨어, 라우터 등록)
│   ├── config.py                   # 환경변수·모델 설정 (API 키, Gemini URL, JWT 키 등)
│   ├── auth.py                     # JWT 발급·검증, 게스트/Google 사용자 관리
│   ├── scenarios_loader.py         # 시나리오 JSON 로딩 + 병력 규모·수비대 자동 추정; CONQUEST_DISPOSITIONS 상수, get_scenario_tpp·get_scenario_reserve_divisor 헬퍼 제공
│   ├── gemini_client.py            # Gemini API 호출 헬퍼
│   ├── requirements.txt
│   ├── .env                        # GOOGLE_API_KEY, SECRET_KEY 설정 (직접 생성 필요)
│   ├── prompt/
│   │   ├── prompt_rules.md         # AI 시스템 프롬프트 — 역할·세계 시뮬레이션·행동 판정·진행 규칙
│   │   ├── prompt_output_format.md # AI 시스템 프롬프트 — 출력 포맷 및 STATE_UPDATE 명세
│   │   └── prompt_examples.md      # AI 시스템 프롬프트 — Few-shot 예시 (씬·장 종결·Tier3)
│   ├── data/
│   │   └── users.json              # 런타임 생성 사용자 데이터 저장소 (.gitignore 대상)
│   ├── engine/
│   │   ├── classifier.py           # LLM 기반 행동 유형 분류 (야전·기습·공성·외교·첩보 등)
│   │   ├── conquest.py             # 거점 점령 감지·주둔군 정규화 (처분 유형별 garrison_modifier 계산·회복)
│   │   ├── context.py              # LLM 컨텍스트 빌더 (시나리오 상태·재정·이벤트·오프닝 NPC)
│   │   ├── defeat.py               # 세력 패퇴 자동 감지 (전력 임계값·거점 보유 조건 기반)
│   │   ├── fiscal.py               # 재정 계산 (월수입·월지출·비축금 자동 갱신; compute_player_fiscal)
│   │   ├── quality.py              # 행동 품질 평가용 보조 컨텍스트 구성 및 LLM 평가
│   │   ├── resolver.py             # 행동·전투·외교 회담 판정 엔진 (4d6, 2d6 페이즈, 품질·지형·날씨·등급 보정)
│   │   ├── tick.py                 # 턴 자동 갱신 (전투 피해 회복·예비 인력 회복·첩보 감쇠·전력 재계산)
│   │   └── turn.py                 # 턴 파싱 (시각·STATE_UPDATE 블록 추출); parse_ym·ts_ym_only 타임스탬프 유틸
│   ├── routers/
│   │   ├── auth.py                 # /api/auth/* 엔드포인트 (게스트·Google 로그인, 설정 조회)
│   │   ├── client_config.py        # /api/config 엔드포인트 (등급 스케일·날씨·지형 메타 상수 노출)
│   │   ├── game.py                 # /api/opening, /api/turn 엔드포인트 (HTTP 레이어만)
│   │   ├── quick_battle.py         # /api/quick-battles, /api/quick-battle/{id}/start
│   │   ├── saves.py                # /api/saves CRUD (JWT 인증 필수, 사용자별 격리)
│   │   └── scenarios.py            # /api/scenarios 엔드포인트
│   └── scenarios/
│       └── {scenario-id}/
│           ├── meta.json           # 표시 메타데이터 (제목·섹션·troops_per_strength_point 등)
│           ├── locations.json      # 거점 목록 (x/y는 SVG 크기 기준 퍼센트 좌표)
│           ├── factions.json       # 세력 목록 (strength_score 직접 지정)
│           ├── characters.json     # 인물 원본 목록 (이름·직위·설명·소속 세력·stats 등)
│           ├── character-select.json # 선택형 시나리오의 주인공 선택 카드 데이터
│           ├── events.json         # 세계 사건 목록
│           ├── event_context.json  # 이벤트 조건 평가 확장 변수 (faction_vars·location_vars)
│           ├── prompt.md           # 시나리오 전역 LLM 지시문 (명령형으로 작성)
│           ├── prompt_{char_id}.md # 캐릭터별 LLM 지시문 (select 모드, 해당 캐릭터 선택 시에만 주입)
│           └── map.svg             # 배경 지도 SVG (선택, 현재 자동 인라인 로딩 대상)
├── frontend/
│   ├── auth.html                   # 진입 화면 (게스트 시작 / Google 로그인)
│   ├── main_menu.html              # 메인 메뉴 (새 게임 / 불러오기)
│   ├── quick-battle.html           # 빠른 역사적 전투 선택 화면
│   ├── scenario_select.html        # 시나리오 선택 화면
│   ├── prince_select.html          # 오스만 공위기 주인공 선택 화면
│   ├── game.html                   # 메인 게임 화면 (HTML 구조만)
│   ├── combat-ui.js                # 다중 페이즈 전투 오버레이 렌더링·전술 입력·후퇴 처리
│   ├── combat-debug.html           # 전투 UI 수동 디버그 페이지
│   ├── diplomacy-ui.js             # 다중 라운드 외교 회담 오버레이 렌더링·입력·중단 처리
│   ├── game-tooltip.js             # 툴팁 시스템 + 태그 스타일 정의
│   ├── game-markdown.js            # 마크다운 → HTML 변환, 응답 텍스트 파싱
│   ├── game-ui.js                  # 렌더링 함수 (씬·인물·세력·지도·사건·능력치 등급)
│   ├── game-turn.js                # 턴 진행(submitTurn), 저장, 선택지 처리, NPC 스탯 자동 배정
│   ├── game-init.js                # 전역 상태 선언 + 게임 초기화 IIFE
│   ├── common.js                   # 공통 유틸 (showComingSoon 토스트 등)
│   ├── api.js                      # 중앙화된 API 클라이언트 (fetch 호출 집중 관리)
│   ├── nav.js                      # 네비게이션·인증 상태 관리 (sessionStorage / localStorage / 쿠키)
│   ├── scenario-loader.js          # 프론트엔드용 시나리오 로더 (브라우저 스크립트)
│   ├── scenario-ui.js              # 프론트엔드용 시나리오 UI 렌더러
│   ├── game.css                    # 게임 UI 스타일
│   └── styles.css                  # 공통 디자인 시스템 (변수, 카드, 애니메이션 등)
├── state/
│   ├── GameState.js                # 게임 상태 클래스 (인물·세력·거점·히스토리)
│   └── StateManager.js             # sessionStorage 직렬화·복원
├── saves/
│   └── {user_id}/                  # 런타임 생성 사용자별 세이브 저장소 (JSON, .gitignore 대상)
├── deploy/
│   ├── setup.sh                    # Oracle Cloud Ubuntu 초기 설정 스크립트
│   ├── update.sh                   # 서버 코드 업데이트 및 서비스 재시작
│   ├── auto-update.sh              # GitHub 커밋 감지 자동 배포 스크립트 (cron)
│   ├── nginx.conf                  # nginx reverse proxy 설정
│   └── interactive-stories.service # systemd 서비스 파일
├── tools/
│   └── map-coord-picker.html       # 지도 이미지 좌표 픽업 도구
├── .gitignore
├── start.bat                       # Windows 실행 스크립트
└── start.sh                        # Mac/Linux 실행 스크립트
```

---

## 현재 시나리오

| ID | 제목 | 배경 | 상태 |
|---|---|---|---|
| `ottoman-interregnum` | 뇌제의 후계자 | 1403년 · 오스만 제국 공위기 (4인 왕자 선택) | 정식 |
| `justinians-dream` | 유스타니우스의 꿈 | 533년 · 동로마 제국 재정복 전쟁 | 정식 |
| `northeast-asia-1189` | 초원의 여명 | 1189년 · 동북아시아·대초원 (5개 세력 선택) | 베타 |

---

## 시작하기

### 테스터 (초대받은 경우)

별도 설치 없이 브라우저로 접속합니다.

1. 공유받은 **서버 URL**을 브라우저에서 열기
2. 초대 코드 입력 후 **게스트로 시작하기**

세이브 데이터는 해당 브라우저에 연결됩니다. 브라우저 데이터를 삭제하면 복구할 수 없습니다.

---

### 로컬 서버 직접 실행

#### 사전 준비

- **Python 3.10 이상** — [python.org/downloads](https://www.python.org/downloads/) (설치 시 "Add Python to PATH" 체크)
- **Google AI Studio API 키** — [aistudio.google.com](https://aistudio.google.com) 에서 무료 발급

#### 실행 방법

**Windows**
```
start.bat 더블클릭
```

**Mac / Linux**
```bash
chmod +x start.sh
./start.sh
```

스크립트가 자동으로:
1. 가상환경 생성 및 패키지 설치 (최초 1회)
2. API 키 미설정 시 `.env` 파일 생성 안내
3. 서버 시작 후 브라우저 자동 오픈 (`http://localhost:8000`)

> `backend/.env` 파일에 아래 항목을 설정합니다.
> ```
> GOOGLE_API_KEY=발급받은_Gemini_키
> SECRET_KEY=랜덤_문자열_64자_이상        # JWT 서명 키 (미설정 시 재시작마다 로그인 초기화)
> # INVITE_CODE=                         # 로컬 개발 시 비워두면 초대 코드 검증 없음
> # GOOGLE_CLIENT_ID=OAuth_클라이언트_ID  # Google 로그인 버튼 활성화 시 필요 (아래 참고)
> ```

#### Google 로그인 버튼 활성화 (선택)

`GOOGLE_CLIENT_ID`를 설정하면 로그인 화면에 **구글로 계속하기** 버튼이 자동으로 나타납니다.

1. [Google Cloud Console](https://console.cloud.google.com/) → **API 및 서비스 → 사용자 인증 정보**
2. **OAuth 2.0 클라이언트 ID 만들기** (유형: 웹 애플리케이션)
3. **승인된 JavaScript 원본** 추가:
   - 로컬 개발: `http://localhost:8000`
4. 발급된 클라이언트 ID를 `.env`에 추가:
   ```
   GOOGLE_CLIENT_ID=123456789-xxxx.apps.googleusercontent.com
   ```

#### 수동 실행

```bash
# 최초 1회
python -m venv .venv
.venv/Scripts/pip install -r backend/requirements.txt  # Mac/Linux: .venv/bin/pip

# 서버 실행
cd backend
uvicorn main:app --reload --port 8000
# 브라우저에서 http://localhost:8000 접속
```

---

## 게임 플레이 흐름

1. **로그인** — 초대 코드(서버 설정 시)를 입력한 뒤 게스트로 시작하거나 Google 계정으로 로그인. 게스트는 브라우저에 UUID를 저장해 재접속 시 동일 계정 유지
2. **시나리오 선택** — 프리셋 시나리오 선택. 커스텀 시나리오 입력은 미구현
3. **주인공 선택** — 시나리오에 따라 플레이어블 캐릭터 선택 (선택형 시나리오)
4. **씬 진행** — AI가 상황을 묘사하고 최대 3개의 선택지를 제시
5. **명령 입력** — 선택지를 고르거나 자유 텍스트로 직접 명령 입력
6. **전투 진행** — 군사 행동이 전투로 분류되면 전투 오버레이에서 페이즈 단위로 전술 명령 입력
7. **외교 회담** — 고위급 협상은 현재 일반 씬으로 처리됨 (전용 외교 오버레이 개발 예정)
8. **상태 변화 누적** — 전투 피해, 외교 관계, 재정, 예비 인력, 거점 지배 상태가 턴마다 갱신

빠른 역사적 전투를 선택하면 시나리오·주인공 선택 단계를 건너뛰고 사전 정의된 전장으로 바로 진입합니다.

---

## 시나리오 추가 방법

1. `backend/scenarios/` 아래 새 폴더 생성 (예: `my-scenario/`)
2. `meta.json` 작성 (기존 시나리오 참고)
3. `locations.json`, `factions.json`, `characters.json` 등 필요한 파일 작성
   - `characters.json`의 주요 인물에 `stats` 필드 작성 (`{"통솔": "B+", "지략": "C", ...}`)
4. 선택형 시나리오라면 `character-select.json`을 작성해 선택 카드, 플레이 가능 여부, 추천 표시 등을 정의
5. `map.svg` 배치 — 시나리오 폴더에 넣으면 게임 화면에 자동 표시됨  
   좌표가 없는 경우 `tools/map-coord-picker.html`을 브라우저에서 열어 이미지를 불러온 뒤 위치를 클릭하면 x/y 좌표가 기록되고, JSON 복사 버튼으로 `locations.json`에 바로 붙여넣기 가능
6. `prompt.md` 작성 — 시나리오 전역 LLM 지시 (명령형). select 모드는 `prompt_{char_id}.md`도 작성
7. `scenario-ui.js`의 `CONFIGS`에 시나리오 ID 키로 UI 설정 추가
8. 백엔드 서버 재시작 시 자동으로 목록에 포함됨
