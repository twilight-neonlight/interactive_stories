"""
routers/saves.py — 세이브 파일 CRUD API
"""

from fastapi import APIRouter, HTTPException, Request
from pathlib import Path
from datetime import datetime
import json

SAVES_DIR = Path(__file__).parent.parent.parent / "saves"
SAVES_DIR.mkdir(exist_ok=True)

router = APIRouter(prefix="/api/saves")


def _get_save_path(filename: str) -> Path:
    path = SAVES_DIR / filename
    if not path.exists() or path.suffix != ".json":
        raise HTTPException(status_code=404, detail="저장 파일을 찾을 수 없습니다.")
    return path


@router.get("")
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


@router.post("")
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


@router.get("/{filename}")
def get_save(filename: str):
    return json.loads(_get_save_path(filename).read_text(encoding="utf-8"))


@router.delete("/{filename}")
def delete_save(filename: str):
    _get_save_path(filename).unlink()
    return {"ok": True}
