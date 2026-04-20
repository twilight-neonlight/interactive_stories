# Interactive Stories

**역사·창작 세계를 배경으로 한 AI 기반 인터랙티브 전쟁·정치 시뮬레이션 게임**

플레이어의 선택이 세계를 바꾼다. 역사의 분기점에 서서 군사·외교·내정 판단을 내리고, AI가 그 결과를 세계에 반영한다.

---

## 기능 개요

### 시나리오 시스템
- 프리셋 시나리오와 **자유 커스텀 시나리오** 모두 지원
- 커스텀 시나리오: 시대, 세계관, 지휘관, 목표, 주요 위협을 자유 텍스트로 입력해 즉시 시작
- 시나리오마다 고유한 배경 지도, 세력 배치, 등장 인물 설정 보유
- 주인공 선택형(`protagonistMode: select`) / 고정형(`fixed`) 분기 지원
- 시나리오 데이터(`backend/scenarios/{id}/`)는 JSON 파일로 분리 관리 — 코드 수정 없이 편집 가능

### AI 내러티브 엔진 (TurnEngine)
- Google Gemini(`gemini-3-flash-preview`)를 내러티브 생성 모델로 사용
- 플레이어 입력 → 백엔드 `/api/turn` → AI 응답 → 상태 갱신의 단방향 흐름
- 행동 판정 5단계: **대성공 / 성공 / 부분 성공 / 실패 / 대실패** — 주사위(1–100) + 병력·외교·지형 수정치로 결정
- 병력 비교에 중립 구간(0.91–1.09배) 적용 — 호각 전투에서 불필요한 열세 패널티 없음
- 장(Chapter) / 씬(Scene) 구조 자동 추적: LLM 응답 텍스트에서 `## N장, SCENE M` 패턴을 파싱해 진행 위치를 갱신

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
| `strength_score` | 0 – 700 | 병력·영토·자원을 반영하는 기반 점수 (영구적) |
| `battle_damage` | 0 이상 | 전투 패배로 누적되는 임시 페널티 (시간 경과로 회복) |

실효 강도 = `strength_score − battle_damage` → 아래 7단계 레이블로 표시.

`meta.json`에 `troops_per_strength_point` 값을 설정하면 강도 점수를 추정 병력 수(±20% 범위)로 변환해 UI와 LLM 컨텍스트에 표시합니다. 미설정 시 시나리오의 연도·동서양 배경에서 자동 추정합니다.

| 레이블 | 실효 점수 |
|---|---|
| `extreme` | 600 이상 |
| `very high` | 500 – 599 |
| `high` | 400 – 499 |
| `medium` | 300 – 399 |
| `low` | 200 – 299 |
| `very low` | 100 – 199 |
| `impotent` | 0 – 99 |

**세력 외교 (`factions` — diplomacy)**

| 속성 | 범위 | 설명 |
|---|---|---|
| `diplomacy_score` | −100 – +100 | 플레이어에 대한 우호도 수치 |
| `disposition` | 우호 / 중립 / 적대 | 수치에서 자동 산출 |

수치 → 태도 변환 기준:

- `> 33` → **우호**
- `−33 ~ 33` → **중립**
- `< −33` → **적대**

초기값: 우호 → 50, 중립 → 0, 적대 → −50. `faction_diplomacy_changes`로 delta 누적 시 태도 자동 재계산. `faction_disposition_changes`로 태도를 직접 설정하면 점수도 해당 초기값으로 보정됩니다.

**거점 (`locations`)**
- `controller`: 현재 지배 세력 id
- 게임 중 점거·해방 시 `location_changes`로 갱신

**대화 히스토리**
- 전체 턴 히스토리를 `{role, content}[]` 형태로 유지해 맥락 연속성 보장
- 게임 상태는 `sessionStorage`에 직렬화(JSON)되어 세션 간 복원 지원

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
| `character_troop_changes` | 인물 병력 변경 (delta) |
| `character_disposition_changes` | 인물 성향 변경 |
| `new_locations` / `location_changes` | 거점 추가·지배 세력 변경 |

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

---

## 기술 스택

| 구분 | 사용 기술 |
|---|---|
| 프론트엔드 | Vanilla HTML / CSS / JavaScript |
| 백엔드 | Python, FastAPI, Uvicorn |
| AI 모델 | Google Gemini (`gemini-3-flash-preview`) |
| 상태 저장 | sessionStorage (클라이언트) |
| 패키지 관리 | pip / venv |

---

## 프로젝트 구조

```
interactive_stories/
├── backend/
│   ├── main.py                     # FastAPI 앱 팩토리 (미들웨어, 라우터 등록)
│   ├── config.py                   # 환경변수·모델 설정 (API 키, Gemini URL 등)
│   ├── scenarios_loader.py         # 시나리오 JSON 로딩 + 병력 규모 자동 추정
│   ├── gemini_client.py            # Gemini API 호출 헬퍼
│   ├── requirements.txt
│   ├── .env                        # GOOGLE_API_KEY 설정 (직접 생성 필요)
│   ├── engine/
│   │   ├── resolver.py             # 행동 판정 엔진 (키워드 분류, 지형·병력 수정치, 5단계 등급)
│   │   ├── turn.py                 # 턴 파싱 (장/씬 번호, 시각, STATE_UPDATE 블록 추출)
│   │   └── context.py              # LLM 컨텍스트 빌더 (시나리오 상태 주입, 오프닝 NPC)
│   ├── routers/
│   │   ├── scenarios.py            # /api/scenarios 엔드포인트
│   │   ├── saves.py                # /api/saves CRUD
│   │   └── game.py                 # /api/opening, /api/turn 엔드포인트
│   └── scenarios/
│       └── {scenario-id}/
│           ├── meta.json           # 표시 메타데이터 (제목·섹션·troops_per_strength_point 등)
│           ├── locations.json      # 거점 목록 (x/y는 이미지 기준 퍼센트 좌표)
│           ├── factions.json       # 세력 목록 (strength_score 직접 지정)
│           ├── characters.json     # 인물 목록 (playable: true/false로 선택 가능 여부 지정)
│           ├── events.json         # 세계 사건 목록
│           ├── npc-pool.json       # NPC 풀 (가중치·거점 조건부 등장 지원)
│           └── map.png             # 배경 지도 이미지 (선택, PNG/JPG/WEBP 모두 가능)
├── frontend/
│   ├── main_menu.html              # 메인 메뉴 (새 게임 / 불러오기)
│   ├── scenario_select.html        # 시나리오 선택 화면
│   ├── prince_select.html          # 주인공 선택 화면
│   ├── game.html                   # 메인 게임 화면 (HTML 구조만)
│   ├── game-tooltip.js             # 툴팁 시스템 + 태그 스타일 정의
│   ├── game-markdown.js            # 마크다운 → HTML 변환, 응답 텍스트 파싱
│   ├── game-ui.js                  # 렌더링 함수 (씬·인물·세력·지도·사건)
│   ├── game-turn.js                # 턴 진행(submitTurn), 저장, 선택지 처리
│   ├── game-init.js                # 전역 상태 선언 + 게임 초기화 IIFE
│   ├── common.js                   # 공통 유틸 (showComingSoon 토스트 등)
│   ├── api.js                      # 중앙화된 API 클라이언트 (fetch 호출 집중 관리)
│   ├── nav.js                      # 네비게이션 상태 관리 (sessionStorage 키 집중 관리)
│   ├── game.css                    # 게임 UI 스타일
│   └── styles.css                  # 공통 디자인 시스템 (변수, 카드, 애니메이션 등)
├── state/
│   ├── GameState.js                # 게임 상태 클래스 (인물·세력·거점·히스토리)
│   └── StateManager.js             # sessionStorage 직렬화·복원
├── saves/                          # 서버 측 세이브 파일 저장소 (JSON)
├── tools/
│   └── map-coord-picker.html       # 지도 이미지 좌표 픽업 도구
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

> API 키는 `backend/.env` 파일에 `GOOGLE_API_KEY=발급받은키` 형식으로 저장합니다.

### 수동 실행 (개발자용)

```bash
# 최초 1회
python -m venv .venv
.venv/Scripts/pip install -r backend/requirements.txt  # Mac/Linux: .venv/bin/pip

# 서버 실행
cd backend
uvicorn main:app --reload --port 8000
# 브라우저에서 http://localhost:8000 접속
```

### 지도 이미지 추가 (선택)

시나리오 폴더(`backend/scenarios/{id}/`)에 `map.png`(또는 `.jpg`, `.webp`)를 넣으면 게임 화면에 자동으로 표시됩니다.

좌표가 없는 경우 `tools/map-coord-picker.html`을 브라우저에서 열어 좌표를 확인할 수 있습니다:
1. 도구에서 지도 이미지를 불러옴
2. 원하는 위치를 클릭하면 x%, y% 좌표 기록
3. JSON 복사 버튼으로 `locations.json`에 바로 붙여넣기 가능

---

## 게임 플레이 흐름

1. **시나리오 선택** — 프리셋 시나리오 선택 또는 커스텀 시나리오 직접 입력
2. **주인공 선택** — 시나리오에 따라 플레이어블 캐릭터 선택 (선택형 시나리오)
3. **씬 진행** — AI가 상황을 묘사하고 2~4개의 선택지를 제시
4. **명령 입력** — 선택지를 고르거나 자유 텍스트로 직접 명령 입력
5. **장 종결** — 핵심 갈등이 새로운 균형에 도달하면 장이 종결되고 요약·총평 제공
6. **다음 장** — 플레이어 입력을 받아 다음 장으로 이어짐

---

## 시나리오 추가 방법

1. `backend/scenarios/` 아래 새 폴더 생성 (예: `my-scenario/`)
2. `meta.json` 작성 (기존 시나리오 참고)
3. `locations.json`, `factions.json`, `characters.json` 등 필요한 파일 작성
4. `map.png` 배치 + `tools/map-coord-picker.html`로 좌표 확보
5. `scenario-ui.js`의 `CONFIGS`에 시나리오 ID 키로 UI 설정 추가
6. 백엔드 서버 재시작 시 자동으로 목록에 포함됨
