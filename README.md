# Interactive Stories

**역사·창작 세계를 배경으로 한 AI 기반 인터랙티브 전쟁·정치 시뮬레이션 게임**

플레이어의 선택이 세계를 바꾼다. 역사의 분기점에 서서 군사·외교·내정 판단을 내리고, AI가 그 결과를 세계에 반영한다.

---

## 기능 개요

### 시나리오 시스템
- 프리셋 시나리오 중심으로 지원
- 커스텀 시나리오 입력 UI는 존재하지만, 현재 버전에서는 게임 초기화 흐름과 완전히 연결되지 않은 실험 기능
- 시나리오마다 고유한 배경 지도, 세력 배치, 등장 인물 설정 보유
- 주인공 선택형(`protagonistMode: select`) / 고정형(`fixed`) 분기 지원
- 시나리오 데이터(`backend/scenarios/{id}/`)는 JSON 파일로 분리 관리 — 코드 수정 없이 편집 가능
- 선택형 시나리오는 `character-select.json`에서 선택 카드 데이터를 관리하고, `characters.json`의 인물 원본 데이터와 조합해 표시

### AI 내러티브 엔진 (TurnEngine)
- Google Gemini(`gemini-3-flash-preview`)를 내러티브 생성 모델로 사용
- 플레이어 입력 → 백엔드 `/api/turn` → AI 응답 → 상태 갱신의 단방향 흐름
- 행동 판정 5단계: **대성공 / 성공 / 부분 성공 / 실패 / 대실패**
- 일반 행동 판정은 **4d6 + 보정치**로 결정하며, 행동 품질 평가(`!!`, `!`, `=`, `?`, `??`)가 최대 ±4 범위의 수정치로 반영됨
- 군사·외교·첩보 행동은 LLM 기반 행동 분류기와 품질 평가기를 거치며, 군사 행동은 지형·날씨·수비대 보정도 함께 반영
- 수동적 관찰·대기 등은 별도 주사위 판정 없이 서술형으로 처리
- 장(Chapter) / 씬(Scene) 구조 자동 추적: LLM 응답 텍스트에서 `## N장, SCENE M` 패턴을 파싱해 진행 위치를 갱신

### 다중 페이즈 전투 시스템
- 야전·기습·공성 행동은 즉시 단일 결과로 끝나지 않고 전투 오버레이(`combat-ui.js`)로 진입
- 전투 시작 시 `combatState`를 생성해 양측 전력, 사기, 페이즈 번호, 적 예고 행동, 누적 피해를 추적
- 전투 전용 우연 변수는 **4d6**으로 산출되며, 전술 판단을 뒤집기보다 박빙 상황·피해 규모·우발 사건에 제한적으로 반영
- 각 페이즈에서 LLM은 `phase_outcome`을 출력하고, 다음 페이즈 시작 시 사기와 전투 피해가 적용됨
- 사기(`player_morale` / `enemy_morale`)는 0–100 범위이며, 전투 오버레이 상단 막대에 현재 전황 지표로 표시
- `combat_victor`는 최소 교전 페이즈 이후에만 수용하며, 플레이어는 언제든 후퇴를 선택할 수 있음
- 전투 종료 시 누적 `pending_battle_damage`가 `faction_battle_damage`로 확정되어 세력 전력과 병력 수에 반영

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
- 게임 중 동적 추가된 인물에는 `is_dynamic: true` 플래그

**세력 강도 (`factions` — strength)**

세력 강도는 두 값의 합산으로 결정됩니다:

| 속성 | 범위 | 설명 |
|---|---|---|
| `strength_score` | 병력·영토·자원을 반영하는 기반 점수 (영구적) |
| `battle_damage` | 전투 패배로 누적되는 임시 페널티 (시간 경과로 회복) |

실효 강도 = `strength_score − battle_damage` → 아래 7단계 레이블로 표시.

`meta.json`에 `troops_per_strength_point` 값을 설정하면 강도 점수를 추정 병력 수(±20% 범위)로 변환해 UI와 LLM 컨텍스트에 표시합니다. 미설정 시 시나리오의 연도·동서양 배경에서 자동 추정합니다.

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
- `enemy_next_action`: 다음 페이즈 적 예고 행동
- `pending_phase_outcome`: 직전 장면의 결과. 다음 페이즈 시작 시 사기·피해로 적용
- `pending_battle_damage`: 전투 중 누적 피해. 전투 종료 시 `faction_battle_damage`로 확정
- `is_siege`, `siege_location_id`, `siege_garrison`: 공성전 전용 정보

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
| `faction_strength_changes` | 세력 기반 강도 변경 (delta, 영구적) |
| `faction_battle_damage` / `faction_battle_recovery` | 전투 피해 누적·회복 (임시적) |
| `faction_diplomacy_changes` | 외교 수치 변경 (delta → 태도 자동 재계산) |
| `faction_disposition_changes` | 외교 태도 직접 설정 |
| `faction_intel_changes` | 세력 첩보 수준 변경 (0–4 범위로 clamp) |
| `character_troop_changes` | 인물 병력 변경 (delta) |
| `character_disposition_changes` | 인물 성향 변경 |
| `character_title_changes` | 인물 직위·칭호 변경 (즉위·승진·폐위 등) |
| `new_locations` / `location_changes` | 거점 추가·지배 세력 변경 |
| `weather` | 현재 날씨 설정. 군사 판정의 날씨 보정에 사용 |
| `combat_state` | 전투 시작·진행·종결 상태 갱신 |

전투 진행 중에는 일반 `faction_battle_damage`를 즉시 수용하지 않고, 엔진이 `phase_outcome`과 `pending_battle_damage`를 통해 피해를 관리합니다. 전투 관련 LLM 출력에는 `phase_outcome`, `combat_victor`, `enemy_next_action`, `player_coalition`, `enemy_coalition`이 사용됩니다.

### 지도 시스템
- 실제 역사 지도 이미지(PNG/JPG/WEBP)를 시나리오 폴더에 배치하면 자동으로 적용
- 거점 좌표는 이미지 크기 대비 퍼센트(`0–100`)로 저장 → 해상도·비율 변화에 무관하게 정확히 위치
- CSS 절대 위치 마커 + 펄스 애니메이션으로 렌더링
- 마커 색상: 본국 영토(초록) / 동맹 거점(파랑) / 적 점거(빨강) / 불안정(주황) / 중립(회색) — 시나리오별 커스터마이즈 가능
- `tools/map-coord-picker.html`을 브라우저에서 열어 이미지를 불러온 뒤 클릭하면 좌표를 바로 기록·복사 가능

### NPC 풀 시스템
- 시나리오마다 `npc-pool.json`에 등장 가능한 인물 풀을 정의
- 게임 시작 시 플레이어 역할에 따라 자동 소환: **군주·영주는 3–5명** (성향 다양성 보장), **일반 장군은 1–2명**
- 각 NPC 항목에 `weight`(가중치), `tags`(역할 분류), `start_eligible`(시작 시 소환 여부), `require_location`(특정 거점 통제 시에만 등장) 속성 지원
- 이벤트 진행 중 새 인물이 필요할 때 AI가 풀을 참조해 가중치 기반으로 선택

### 게임 UI (3열 레이아웃)
| 영역 | 내용 |
|---|---|
| 좌측 | 지휘관 프로필(1) · 주요 인물 목록(2) · 세력 현황 바(2) — flex 비율 1:2:2 |
| 중앙 | 씬 본문(마크다운 렌더링), 장·씬 배지, 시각·장소 표시 |
| 우측 | 배경 지도(이미지 + CSS 마커), 동시 진행 사건, 선택지 버튼 + 자유 입력창 |

- 지휘관 프로필: 직위·병력(추정 수치 범위)·거점을 표시
- 지도 마커·세력 현황 바 툴팁에 세력 고유 색상 도트 표시
- 인물·지도 마커·사건 항목에 **호버 툴팁** 제공 (세부 정보 표시)
- 장 종결 후 요약 테이블·총평·잔불 전용 화면으로 전환
- 전투 발생 시 전용 오버레이로 전환해 사기 막대, 교전 기록, 판정 배지, 후퇴 버튼, 전술 명령 입력창 표시
- 판정 배지는 일반 행동 등급 또는 전투 우연 변수를 표시하며, 툴팁에서 4d6 결과와 보정 정보를 확인 가능

---

## 기술 스택

| 구분 | 사용 기술 |
|---|---|
| 프론트엔드 | Vanilla HTML / CSS / JavaScript |
| 백엔드 | Python, FastAPI, Uvicorn |
| AI 모델 | Google Gemini (`gemini-3-flash-preview`) |
| 인증 | JWT (python-jose) — 게스트 UUID / Google OAuth 2.0 |
| 상태 저장 | sessionStorage (진행 중 게임 상태) / 서버 JSON 세이브 / localStorage + 쿠키 (인증 토큰·게스트 UUID) |
| 패키지 관리 | pip / venv |

---

## 프로젝트 구조

```
interactive_stories/
├── backend/
│   ├── main.py                     # FastAPI 앱 팩토리 (미들웨어, 라우터 등록)
│   ├── config.py                   # 환경변수·모델 설정 (API 키, Gemini URL, JWT 키 등)
│   ├── auth.py                     # JWT 발급·검증, 게스트/Google 사용자 관리
│   ├── scenarios_loader.py         # 시나리오 JSON 로딩 + 병력 규모·수비대 자동 추정
│   ├── gemini_client.py            # Gemini API 호출 헬퍼
│   ├── requirements.txt
│   ├── .env                        # GOOGLE_API_KEY, SECRET_KEY 설정 (직접 생성 필요)
│   ├── data/
│   │   └── users.json              # 사용자 데이터 저장소 (게스트·Google 계정)
│   ├── engine/
│   │   ├── classifier.py           # LLM 기반 행동 유형 분류 (야전·기습·공성·외교·첩보 등)
│   │   ├── quality.py              # 행동 품질 평가용 보조 컨텍스트 구성 및 LLM 평가
│   │   ├── resolver.py             # 행동·전투 판정 엔진 (4d6, 품질·지형·날씨·수비대 보정, 전투 페이즈)
│   │   ├── turn.py                 # 턴 파싱 (장/씬 번호, 시각, STATE_UPDATE 블록 추출)
│   │   └── context.py              # LLM 컨텍스트 빌더 (시나리오 상태 주입, 오프닝 NPC)
│   ├── routers/
│   │   ├── auth.py                 # /api/auth/* 엔드포인트 (게스트·Google 로그인, 설정 조회)
│   │   ├── scenarios.py            # /api/scenarios 엔드포인트
│   │   ├── saves.py                # /api/saves CRUD (JWT 인증 필수, 사용자별 격리)
│   │   ├── game.py                 # /api/opening, /api/turn 엔드포인트
│   │   └── quick_battle.py         # /api/quick-battles, /api/quick-battle/{id}/start
│   └── scenarios/
│       └── {scenario-id}/
│           ├── meta.json           # 표시 메타데이터 (제목·섹션·troops_per_strength_point 등)
│           ├── locations.json      # 거점 목록 (x/y는 이미지 기준 퍼센트 좌표)
│           ├── factions.json       # 세력 목록 (strength_score 직접 지정)
│           ├── characters.json     # 인물 원본 목록 (이름·직위·설명·소속 세력 등)
│           ├── character-select.json # 선택형 시나리오의 주인공 선택 카드 데이터
│           ├── events.json         # 세계 사건 목록
│           ├── event_context.json  # 이벤트 조건 평가에 노출할 보조 변수 목록 (선택)
│           ├── rules.json          # 시나리오별 진행·역사 규칙
│           ├── npc-pool.json       # NPC 풀 (가중치·거점 조건부 등장 지원)
│           ├── map.png             # 배경 지도 이미지 (선택, PNG/JPG/WEBP 모두 가능)
│           └── map_preview.html    # 시나리오별 지도 미리보기/검수용 HTML (선택)
├── frontend/
│   ├── auth.html                   # 진입 화면 (게스트 시작 / Google 로그인)
│   ├── main_menu.html              # 메인 메뉴 (새 게임 / 불러오기)
│   ├── quick-battle.html           # 빠른 역사적 전투 선택 화면
│   ├── scenario_select.html        # 시나리오 선택 화면
│   ├── prince_select.html          # 주인공 선택 화면
│   ├── character_select_deluge.html # 델루지 시나리오 전용 주인공 선택 화면
│   ├── game.html                   # 메인 게임 화면 (HTML 구조만)
│   ├── combat-ui.js                # 다중 페이즈 전투 오버레이 렌더링·전술 입력·후퇴 처리
│   ├── game-tooltip.js             # 툴팁 시스템 + 태그 스타일 정의
│   ├── game-markdown.js            # 마크다운 → HTML 변환, 응답 텍스트 파싱
│   ├── game-ui.js                  # 렌더링 함수 (씬·인물·세력·지도·사건)
│   ├── game-turn.js                # 턴 진행(submitTurn), 저장, 선택지 처리
│   ├── game-init.js                # 전역 상태 선언 + 게임 초기화 IIFE
│   ├── common.js                   # 공통 유틸 (showComingSoon 토스트 등)
│   ├── api.js                      # 중앙화된 API 클라이언트 (fetch 호출 집중 관리)
│   ├── nav.js                      # 네비게이션·인증 상태 관리 (sessionStorage / localStorage / 쿠키)
│   ├── game.css                    # 게임 UI 스타일
│   └── styles.css                  # 공통 디자인 시스템 (변수, 카드, 애니메이션 등)
├── state/
│   ├── GameState.js                # 게임 상태 클래스 (인물·세력·거점·히스토리)
│   └── StateManager.js             # sessionStorage 직렬화·복원
├── saves/
│   └── {user_id}/                  # 사용자별 격리된 세이브 파일 저장소 (JSON)
├── tools/
│   └── map-coord-picker.html       # 지도 이미지 좌표 픽업 도구
├── .gitignore
├── scenario-loader.js              # 백엔드 REST API 클라이언트
├── scenario-ui.js                  # 시나리오별 UI 렌더링 로직 (색상·마커·NPC 소환)
├── prompt_rules.md                 # AI 시스템 프롬프트 — 역할·세계 시뮬레이션·행동 판정·진행 규칙
├── prompt_output_format.md         # AI 시스템 프롬프트 — 출력 포맷 및 STATE_UPDATE 명세
├── prompt_examples.md              # AI 시스템 프롬프트 — Few-shot 예시 (씬·장 종결·Tier3)
├── start.bat                       # Windows 실행 스크립트
└── start.sh                        # Mac/Linux 실행 스크립트
```

---

## 시작하기

### 사전 준비

- **Python 3.10 이상** — [python.org/downloads](https://www.python.org/downloads/) (설치 시 "Add Python to PATH" 체크)
- **Google AI Studio API 키** — [aistudio.google.com](https://aistudio.google.com) 에서 무료 발급

### 실행 방법

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

Windows용 `start.bat`는 실행 시 GitHub 최신 버전 확인과 자동 업데이트 안내도 수행합니다.

> `backend/.env` 파일에 아래 항목을 설정합니다.
> ```
> GOOGLE_API_KEY=발급받은_Gemini_키
> SECRET_KEY=랜덤_문자열_64자_이상        # JWT 서명 키 (미설정 시 재시작마다 로그인 초기화)
> GOOGLE_CLIENT_ID=OAuth_클라이언트_ID    # Google 로그인 사용 시만 필요 (선택)
> ```

### 수동 실행 (개발자용)

```bash
# 최초 1회
python -m venv .venv
.venv/Scripts/pip install -r backend/requirements.txt  # Mac/Linux: .venv/bin/pip

# 서버 실행
cd backend
uvicorn main:app --reload --port 8000
# 브라우저에서 http://localhost:8000 접속
# 루트 경로는 /frontend/main_menu.html로 리다이렉트됩니다.
```

### 지도 이미지 추가 (선택)

시나리오 폴더(`backend/scenarios/{id}/`)에 `map.png`(또는 `.jpg`, `.webp`)를 넣으면 게임 화면에 자동으로 표시됩니다.

좌표가 없는 경우 `tools/map-coord-picker.html`을 브라우저에서 열어 좌표를 확인할 수 있습니다:
1. 도구에서 지도 이미지를 불러옴
2. 원하는 위치를 클릭하면 x%, y% 좌표 기록
3. JSON 복사 버튼으로 `locations.json`에 바로 붙여넣기 가능

---

## 게임 플레이 흐름

1. **로그인** — 게스트로 시작하거나 Google 계정으로 로그인. 게스트는 브라우저에 UUID를 저장해 재접속 시 동일 계정 유지
2. **시나리오 선택** — 프리셋 시나리오 선택. 커스텀 입력 UI는 있으나 현재 게임 시작 흐름에는 아직 연결되지 않음
3. **주인공 선택** — 시나리오에 따라 플레이어블 캐릭터 선택 (선택형 시나리오)
4. **씬 진행** — AI가 상황을 묘사하고 2~4개의 선택지를 제시
5. **명령 입력** — 선택지를 고르거나 자유 텍스트로 직접 명령 입력
6. **전투 진행** — 군사 행동이 전투로 분류되면 전투 오버레이에서 페이즈 단위로 전술 명령 입력
7. **장 종결** — 핵심 갈등이 새로운 균형에 도달하면 장이 종결되고 요약·총평 제공
8. **다음 장** — 플레이어 입력을 받아 다음 장으로 이어짐

빠른 역사적 전투를 선택하면 시나리오·주인공 선택 단계를 건너뛰고 사전 정의된 전장으로 바로 진입합니다.

---

## 시나리오 추가 방법

1. `backend/scenarios/` 아래 새 폴더 생성 (예: `my-scenario/`)
2. `meta.json` 작성 (기존 시나리오 참고)
3. `locations.json`, `factions.json`, `characters.json` 등 필요한 파일 작성
4. 선택형 시나리오라면 `character-select.json`을 작성해 선택 카드, 플레이 가능 여부, 추천 표시 등을 정의
5. `map.png` 배치 + `tools/map-coord-picker.html`로 좌표 확보
6. `scenario-ui.js`의 `CONFIGS`에 시나리오 ID 키로 UI 설정 추가
7. 백엔드 서버 재시작 시 자동으로 목록에 포함됨
