# Interactive Stories

**역사·창작 세계를 배경으로 한 AI 기반 인터랙티브 전쟁·정치 시뮬레이션 게임**

플레이어의 선택이 세계를 바꾼다. 역사의 분기점에 서서 군사·외교·내정 판단을 내리고, AI가 그 결과를 세계에 반영한다.

---

## 기능 개요

### 시나리오 시스템
- 프리셋 시나리오와 **자유 커스텀 시나리오** 모두 지원
- 커스텀 시나리오: 시대, 세계관, 지휘관, 목표를 자유 텍스트로 입력해 즉시 시작
- 시나리오마다 고유한 배경 지도, 세력 배치, 등장 인물 설정 보유
- 주인공 선택형(`protagonistMode: select`) / 고정형(`fixed`) 분기 지원

### AI 내러티브 엔진 (TurnEngine)
- Google Gemini(`gemini-3-flash-preview`)를 내러티브 생성 모델로 사용
- 플레이어 입력 → 백엔드 `/api/turn` → AI 응답 → 상태 갱신의 단방향 흐름
- 행동 판정 3단계: **Tier 1(실행)** / **Tier 2(난이도 높음)** / **Tier 3(불가 — 세계관 내 이유로 설명)**
- 장(Chapter) / 씬(Scene) 구조 자동 추적: LLM 응답 텍스트에서 `##N장, SCENE M` 패턴을 파싱해 진행 위치를 갱신

### 상태 관리 (GameState / StateManager)
- **인물**: 등장·사망·추방 상태 추적, 게임 중 동적 추가
- **세력**: 군사·경제 역량(`extreme` ~ `impotent`) 실시간 변동
- **거점**: 지배 세력 변경 반영, 지형 정보 보유
- **대화 히스토리**: 전체 턴 히스토리를 유지해 맥락 연속성 보장
- 게임 상태는 `sessionStorage`에 직렬화(JSON)되어 세션 간 복원 지원

### 상태 자동 업데이트 (STATE_UPDATE 블록)
LLM이 씬 응답 끝에 구조화된 블록을 포함하면, 백엔드가 이를 파싱해 프론트엔드에 전달:
- `new_characters` / `dead_characters`
- `new_factions` / `faction_strength_changes`
- `new_locations` / `location_changes`

### 게임 UI (3열 레이아웃)
| 영역 | 내용 |
|---|---|
| 좌측 | 지휘관 프로필, 주요 인물 목록, 세력 현황 바 |
| 중앙 | 씬 본문(마크다운 렌더링), 장·씬 배지, 시각·장소 표시 |
| 우측 | 배경 지도(SVG), 동시 진행 사건, 선택지 버튼 + 자유 입력창 |

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
│   ├── main.py            # FastAPI 서버 (TurnEngine, 시나리오 컨텍스트 빌더)
│   ├── requirements.txt
│   └── .env               # GOOGLE_API_KEY 설정 (직접 생성 필요)
├── state/
│   ├── GameState.js       # 게임 상태 클래스 (인물·세력·거점·히스토리)
│   └── StateManager.js    # sessionStorage 직렬화·복원
├── scenario-loader.js     # 시나리오 JSON 로드 및 그룹핑
├── scenario-ui.js         # 시나리오별 UI 설정 (지도 SVG, 색상, 이벤트 등)
├── scenario_select.html   # 시나리오 선택 화면
├── prince_select.html     # 주인공 선택 화면
├── game.html              # 메인 게임 화면
├── game.css               # 게임 UI 스타일
├── styles.css             # 시나리오 선택 화면 스타일
└── system_prompt.txt      # AI 시스템 프롬프트 (세계 시뮬레이션 규칙 정의)
```

---

## 시작하기

### 1. 환경 설정

```bash
cd backend
python -m venv ../.venv
source ../.venv/Scripts/activate  # Windows: ..\.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. API 키 설정

`backend/.env` 파일을 생성하고 Google AI Studio API 키를 입력합니다:

```
GOOGLE_API_KEY=your_api_key_here
```

> Google AI Studio API 키는 [aistudio.google.com](https://aistudio.google.com) 에서 발급받을 수 있습니다.

### 3. 백엔드 서버 실행

```bash
cd backend
uvicorn main:app --reload --port 8000
```

### 4. 게임 실행

브라우저에서 `scenario_select.html`을 열어 시나리오를 선택하면 게임이 시작됩니다.

> 로컬 파일(`file://`) 직접 열기 또는 간단한 정적 서버(예: VS Code Live Server) 모두 지원합니다.

---

## 게임 플레이 흐름

1. **시나리오 선택** — 프리셋 시나리오 선택 또는 커스텀 시나리오 직접 입력
2. **주인공 선택** — 시나리오에 따라 플레이어블 캐릭터 선택 (선택형 시나리오)
3. **씬 진행** — AI가 상황을 묘사하고 2~4개의 선택지를 제시
4. **명령 입력** — 선택지를 고르거나 자유 텍스트로 직접 명령 입력
5. **장 종결** — 핵심 갈등이 새로운 균형에 도달하면 장이 종결되고 요약·총평 제공
6. **다음 장** — 플레이어 입력을 받아 다음 장으로 이어짐
