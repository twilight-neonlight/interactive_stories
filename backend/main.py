"""
backend/main.py

FastAPI 서버 — Google AI Studio (Gemini) API 프록시 + TurnEngine
실행: uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path
import os
import re
import json
import httpx

# ── 시나리오 데이터 로드 ──────────────────────────
# 구조: backend/scenarios/{id}/meta.json + locations.json + factions.json
#                                         + characters.json + events.json
SCENARIOS_DIR = Path(__file__).parent / "scenarios"

def _load_scenarios() -> list[dict]:
    scenarios = []
    for scenario_dir in sorted(SCENARIOS_DIR.iterdir()):
        if not scenario_dir.is_dir():
            continue
        meta_path = scenario_dir / "meta.json"
        if not meta_path.exists():
            continue
        scenario = json.loads(meta_path.read_text(encoding="utf-8"))
        # JSON 배열 파일
        for key in ("locations", "factions", "characters", "events"):
            path = scenario_dir / f"{key}.json"
            scenario[key] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        # JSON 오브젝트 파일
        for key, filename in (("opening", "opening.json"), ("npc_pool", "npc-pool.json")):
            path = scenario_dir / filename
            scenario[key] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        # SVG 지도 (텍스트 그대로)
        map_path = scenario_dir / "map.svg"
        scenario["map_svg"] = map_path.read_text(encoding="utf-8") if map_path.exists() else ""
        scenarios.append(scenario)
    return scenarios

SCENARIOS: list[dict] = _load_scenarios()

# ── 환경 변수 로드 ────────────────────────────────
load_dotenv()
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다. .env 파일을 확인하세요.")

# ── 시스템 프롬프트 로드 ──────────────────────────
PROMPT_PATH = Path(__file__).parent.parent / "system_prompt.txt"
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")

# ── 모델 설정 ─────────────────────────────────────
MODEL       = "gemini-3-flash-preview"
MAX_TOKENS  = 9172
TEMPERATURE = 0.8

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

# ── FastAPI 앱 ────────────────────────────────────
app = FastAPI(title="Interactive Stories API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 개발용 — 배포 시 실제 오리진으로 제한하세요
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── 요청 스키마 ───────────────────────────────────

class Message(BaseModel):
    role: str      # "user" | "assistant"
    content: str

class TurnRequest(BaseModel):
    command: str
    state:   dict
    history: list[Message]


# ── TurnEngine ────────────────────────────────────
# LLM이 반환한 텍스트에서 구조적 신호를 추출해 state_updates를 생성합니다.
# 클라이언트는 이 값을 그대로 적용하므로, LLM 텍스트를 직접 파싱하지 않습니다.

def _extract_timestamp(text: str) -> str:
    """**시각:** 줄을 우선 추출하고, 없으면 본문에서 '연도+장소' 패턴을 탐색합니다."""
    m = re.search(r"\*\*시각:\*\*\s*([^\n]+)", text)
    if m:
        return m.group(1).strip()
    m = re.search(r"\*시각:\*\s*([^\n]+)", text)
    if m:
        return m.group(1).strip()
    m = re.search(r"(\d{3,4}년[^。\n]{2,30}[,，、]\s*[가-힣A-Za-z][^\n]{0,20})", text)
    return m.group(1).strip() if m else ""

def _extract_chapter_title(text: str) -> str:
    """SCENE 1 직전에 오는 짧은 헤딩을 장 제목으로 추출합니다."""
    m = re.search(r"^#{0,3}\s*(.{2,30})\s*$(?=[\s\S]*SCENE\s*1\b)", text, re.MULTILINE)
    if m and "장" not in m.group(1):
        return m.group(1).strip()
    return ""

def turn_engine(content: str, state: dict) -> dict:
    """
    LLM 응답과 현재 state를 받아 다음 state_updates를 반환합니다.
    우선순위: 장 종결 > 새 장 시작 > 씬 진행 > fallback(씬 +1)
    """
    progress       = state.get("progress", {})
    cur_chapter    = progress.get("chapter", 1)
    cur_scene      = progress.get("scene",   1)
    cur_title      = progress.get("chapterTitle", "")

    # ① 장 종결
    if re.search(r"장\s*종결|Chapter\s*\d+\s*Concluded|Chapter\s*Close", content, re.IGNORECASE):
        return {
            "scene":         cur_scene,
            "chapter":       cur_chapter,
            "chapter_title": cur_title,
            "timestamp":     _extract_timestamp(content),
            "is_chapter_end": True,
        }

    # ② 새 장 시작 (SCENE 1)
    m = re.search(r"##\s*(\d+)장,?\s*SCENE\s*1\b", content, re.IGNORECASE)
    if m:
        new_chapter = int(m.group(1))
        return {
            "scene":         1,
            "chapter":       new_chapter,
            "chapter_title": _extract_chapter_title(content),
            "timestamp":     _extract_timestamp(content),
            "is_chapter_end": False,
        }

    # ③ 씬 진행
    m = re.search(r"##\s*\d+장,?\s*SCENE\s*(\d+)", content, re.IGNORECASE)
    if m:
        return {
            "scene":         int(m.group(1)),
            "chapter":       cur_chapter,
            "chapter_title": cur_title,
            "timestamp":     _extract_timestamp(content),
            "is_chapter_end": False,
        }

    # ④ 패턴 미감지 — 씬 +1 fallback
    return {
        "scene":         cur_scene + 1,
        "chapter":       cur_chapter,
        "chapter_title": cur_title,
        "timestamp":     _extract_timestamp(content),
        "is_chapter_end": False,
    }


# ── state_update 블록 추출 ───────────────────────
# LLM이 응답 끝에 포함시킨 ```state_update ... ``` 블록을 파싱하고
# 본문에서 해당 블록을 제거해 반환합니다.

def _extract_state_update(text: str) -> tuple[str, dict]:
    m = re.search(r'\[STATE_UPDATE\]\s*(\{[\s\S]*?\})\s*(?:```|$)', text)
    if not m:
        # 구버전 포맷 호환 (```state_update ... ```)
        m = re.search(r'```state_update\s*([\s\S]*?)\s*```', text)
    if not m:
        return text, {}
    try:
        data = json.loads(m.group(1))
    except Exception:
        data = {}
    cleaned = (text[:m.start()].rstrip() + "\n" + text[m.end():].lstrip()).strip()
    return cleaned, data


# ── 시나리오 컨텍스트 빌더 ───────────────────────
# state에서 시나리오 정보를 추출해 시스템 프롬프트 끝에 추가합니다.
# LLM이 어떤 시나리오를 진행 중인지, 누가 플레이어인지 알 수 있습니다.

def build_scenario_context(state: dict) -> str:
    lines = [
        "",
        "---",
        "# 현재 시나리오 상태 (엔진이 자동 주입)",
        f"시나리오: {state.get('scenarioTitle', '불명')}",
    ]

    # 플레이어 캐릭터
    protagonist_id = state.get("protagonist")
    chars = state.get("characters", {})
    if protagonist_id and protagonist_id in chars:
        c = chars[protagonist_id]
        lines.append(
            f"플레이어: {c.get('name', protagonist_id)}"
            + (f" / {c.get('title') or c.get('epithet', '')}" if c.get('title') or c.get('epithet') else "")
        )

    # 등장 세력
    factions = state.get("factions", {})
    if factions:
        lines.append("\n등장 세력:")
        for f in factions.values():
            note = f.get("notes", "")
            note_short = note[:80] + "…" if len(note) > 80 else note
            score = f.get("diplomacy_score")
            score_str = f" [{int(score):+d}]" if score is not None else ""
            lines.append(
                f"  - {f.get('name', '?')} | {f.get('disposition', '?')}{score_str} | {f.get('strength', '?')}"
                + (f"\n    {note_short}" if note_short else "")
            )

    # 주요 거점
    locations = state.get("locations", {})
    if locations:
        lines.append("\n주요 거점:")
        for loc in locations.values():
            controller = loc.get("controller", "?")
            # controller id → 세력명으로 변환
            if controller in factions:
                controller = factions[controller].get("name", controller)
            lines.append(f"  - {loc.get('name', '?')} | 지배: {controller}")

    # 동시 진행 세계 사건
    events = state.get("events", [])
    if events:
        lines.append("\n동시 진행 사건:")
        for ev in events:
            name   = ev.get("name", "?")
            region = ev.get("region", "")
            body   = ev.get("body", "")
            body_short = body[:80] + "…" if len(body) > 80 else body
            lines.append(
                f"  - {name}" + (f" ({region})" if region else "")
                + (f"\n    {body_short}" if body_short else "")
            )

    # 현재 진행 위치
    progress = state.get("progress", {})
    chapter  = progress.get("chapter", 1)
    scene    = progress.get("scene", 1)
    is_end   = progress.get("isChapterEnd", False)
    ts       = progress.get("timestamp", "")
    lines.append(
        f"\n현재 위치: {chapter}장 SCENE {scene}"
        + (" (장 종결 후 대기 중)" if is_end else "")
        + (f" / {ts}" if ts else "")
    )

    return "\n".join(lines)


# ── 엔드포인트 ────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/scenarios")
def list_scenarios():
    """시나리오 목록 반환 (카드 렌더링용 메타데이터 포함, 게임 데이터 포함)."""
    return SCENARIOS


@app.get("/api/scenarios/{scenario_id}")
def get_scenario(scenario_id: str):
    """단일 시나리오 전체 데이터 반환."""
    scenario = next((s for s in SCENARIOS if s["id"] == scenario_id), None)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"시나리오 '{scenario_id}'를 찾을 수 없습니다.")
    return scenario


@app.get("/api/scenarios/{scenario_id}/map-image")
def get_map_image(scenario_id: str):
    """시나리오 지도 이미지 파일 반환 (PNG, JPG, WEBP 순서로 탐색)."""
    scenario_dir = SCENARIOS_DIR / scenario_id
    for ext in ("png", "jpg", "jpeg", "webp"):
        path = scenario_dir / f"map.{ext}"
        if path.exists():
            return FileResponse(path, media_type=f"image/{ext.replace('jpeg','jpeg')}")
    raise HTTPException(status_code=404, detail=f"시나리오 '{scenario_id}'의 지도 이미지가 없습니다.")

@app.post("/api/turn")
async def process_turn(req: TurnRequest):
    # 1. 시나리오 컨텍스트를 시스템 프롬프트에 동적으로 추가
    full_system = SYSTEM_PROMPT + build_scenario_context(req.state)

    # 2. 메시지 배열 구성 (history + 현재 입력)
    messages = [{"role": "system", "content": full_system}]
    messages += [{"role": m.role, "content": m.content} for m in req.history]
    messages.append({"role": "user", "content": req.command})

    # 3. Google AI Studio (Gemini) 호출
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                GEMINI_URL,
                headers={
                    "Authorization": f"Bearer {GOOGLE_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model":       MODEL,
                    "messages":    messages,
                    "max_tokens":  MAX_TOKENS,
                    "temperature": TEMPERATURE,
                },
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Gemini API 오류: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gemini API 오류: {e}")

    content = resp.json()["choices"][0]["message"]["content"]

    # 4. state_update 블록 추출 및 제거
    content, extra = _extract_state_update(content)

    # 5. TurnEngine: LLM 응답에서 state_updates 추출
    state_updates = turn_engine(content, req.state)

    # 6. state_update 항목 병합
    for key in ("new_characters", "dead_characters", "new_factions",
                "faction_strength_changes", "faction_diplomacy_changes",
                "faction_disposition_changes", "character_disposition_changes",
                "new_locations", "location_changes"):
        if extra.get(key):
            state_updates[key] = extra[key]

    return {
        "content":       content,
        "state_updates": state_updates,
    }


# ── 정적 파일 서빙 ────────────────────────────────
# API 라우트 등록 후 마지막에 마운트해야 API가 우선 매칭됩니다.
# http://localhost:8000 한 곳에서 프론트엔드와 백엔드를 모두 제공합니다.

@app.get("/")
def root():
    return RedirectResponse(url="/frontend/scenario_select.html")

_ROOT_DIR = Path(__file__).parent.parent  # interactive_stories/
app.mount("/", StaticFiles(directory=str(_ROOT_DIR), html=True), name="static")
