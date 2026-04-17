"""
backend/main.py — FastAPI 서버 (Google AI Studio / Gemini 프록시)
실행: uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime
import os
import json
import httpx

from engine.resolver import resolve_action, resolution_prompt
from engine.turn     import turn_engine, extract_state_update, extract_timestamp
from engine.context  import build_scenario_context, build_opening_npc_context, OPENING_INSTRUCTION

# ── 경로 상수 ─────────────────────────────────────
SAVES_DIR    = Path(__file__).parent.parent / "saves"
SAVES_DIR.mkdir(exist_ok=True)
SCENARIOS_DIR = Path(__file__).parent / "scenarios"

# ── 시나리오 데이터 로드 ──────────────────────────
def _load_scenarios() -> list[dict]:
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
        scenarios.append(scenario)
    return scenarios

SCENARIOS: list[dict] = _load_scenarios()

# ── 환경 변수 / 시스템 프롬프트 ──────────────────
load_dotenv()
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다. .env 파일을 확인하세요.")

PROMPT_PATH   = Path(__file__).parent.parent / "system_prompt.txt"
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")

# ── 모델 설정 ─────────────────────────────────────
MODEL       = "gemini-3-flash-preview"
MAX_TOKENS  = 9172
TEMPERATURE = 0.8
GEMINI_URL  = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

# ── FastAPI 앱 ────────────────────────────────────
app = FastAPI(title="Interactive Stories API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── 요청 스키마 ───────────────────────────────────

class Message(BaseModel):
    role: str
    content: str

class TurnRequest(BaseModel):
    command: str
    state:   dict
    history: list[Message]

class OpeningRequest(BaseModel):
    state: dict


# ── Gemini 호출 헬퍼 ──────────────────────────────

async def _call_gemini(messages: list[dict]) -> str:
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                GEMINI_URL,
                headers={
                    "Authorization": f"Bearer {GOOGLE_API_KEY}",
                    "Content-Type":  "application/json",
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
    return resp.json()["choices"][0]["message"]["content"]


# ── 엔드포인트 ────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/scenarios")
def list_scenarios():
    return SCENARIOS


@app.get("/api/scenarios/{scenario_id}")
def get_scenario(scenario_id: str):
    scenario = next((s for s in SCENARIOS if s["id"] == scenario_id), None)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"시나리오 '{scenario_id}'를 찾을 수 없습니다.")
    return scenario


@app.get("/api/scenarios/{scenario_id}/map-image")
def get_map_image(scenario_id: str):
    scenario_dir = SCENARIOS_DIR / scenario_id
    for ext in ("png", "jpg", "jpeg", "webp"):
        path = scenario_dir / f"map.{ext}"
        if path.exists():
            return FileResponse(path, media_type=f"image/{ext.replace('jpeg','jpeg')}")
    raise HTTPException(status_code=404, detail=f"시나리오 '{scenario_id}'의 지도 이미지가 없습니다.")


@app.post("/api/opening")
async def generate_opening(req: OpeningRequest):
    scenario_id   = req.state.get("scenarioId", "")
    scenario_data = next((s for s in SCENARIOS if s["id"] == scenario_id), None)
    npc_pool      = scenario_data.get("npc_pool", {}) if scenario_data else {}

    full_system = (SYSTEM_PROMPT
                   + build_scenario_context(req.state)
                   + build_opening_npc_context(req.state, npc_pool)
                   + OPENING_INSTRUCTION)
    content = await _call_gemini([
        {"role": "system", "content": full_system},
        {"role": "user",   "content": "[게임 시작] 오프닝 장면을 생성하라."},
    ])
    content, extra = extract_state_update(content)
    return {
        "content":       content,
        "timestamp":     extract_timestamp(content),
        "state_updates": {"new_characters": extra.get("new_characters", [])},
    }


@app.post("/api/turn")
async def process_turn(req: TurnRequest):
    resolution  = resolve_action(req.command, req.state)
    full_system = SYSTEM_PROMPT + build_scenario_context(req.state) + resolution_prompt(resolution)

    messages = [{"role": "system", "content": full_system}]
    messages += [{"role": m.role, "content": m.content} for m in req.history]
    messages.append({"role": "user", "content": req.command})

    content = await _call_gemini(messages)
    content, extra = extract_state_update(content)
    state_updates  = turn_engine(content, req.state)

    for key in ("new_characters", "dead_characters", "new_factions", "defeated_factions",
                "faction_strength_changes", "faction_battle_damage", "faction_battle_recovery",
                "faction_diplomacy_changes", "faction_disposition_changes",
                "character_troop_changes", "character_disposition_changes",
                "new_locations", "location_changes"):
        if extra.get(key):
            state_updates[key] = extra[key]

    return {"content": content, "state_updates": state_updates, "resolution": resolution}


# ── 세이브 파일 CRUD ──────────────────────────────

@app.get("/api/saves")
def list_saves():
    saves = []
    for f in sorted(SAVES_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            saves.append({
                "filename":      f.name,
                "scenarioId":    data.get("scenarioId", ""),
                "scenarioTitle": data.get("scenarioTitle", ""),
                "chapter":       data.get("progress", {}).get("chapter", 1),
                "timestamp":     data.get("progress", {}).get("timestamp", ""),
                "savedAt":       datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
            })
        except Exception:
            pass
    return saves

@app.post("/api/saves")
async def create_save(req: Request):
    data        = await req.json()
    scenario_id = data.get("scenarioId", "unknown")
    chapter     = data.get("progress", {}).get("chapter", 1)
    ts          = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename    = f"{scenario_id}_ch{chapter}_{ts}.json"
    (SAVES_DIR / filename).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"filename": filename}

@app.get("/api/saves/{filename}")
def get_save(filename: str):
    path = SAVES_DIR / filename
    if not path.exists() or path.suffix != ".json":
        raise HTTPException(status_code=404, detail="저장 파일을 찾을 수 없습니다.")
    return json.loads(path.read_text(encoding="utf-8"))

@app.delete("/api/saves/{filename}")
def delete_save(filename: str):
    path = SAVES_DIR / filename
    if not path.exists() or path.suffix != ".json":
        raise HTTPException(status_code=404, detail="저장 파일을 찾을 수 없습니다.")
    path.unlink()
    return {"ok": True}


# ── 정적 파일 서빙 ────────────────────────────────

@app.get("/")
def root():
    return RedirectResponse(url="/frontend/main_menu.html")

_ROOT_DIR = Path(__file__).parent.parent
app.mount("/", StaticFiles(directory=str(_ROOT_DIR), html=True), name="static")
