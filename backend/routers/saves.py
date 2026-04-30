"""
routers/saves.py — 세이브 파일 CRUD API (사용자별 격리)
"""

import re
from fastapi import APIRouter, HTTPException, Request, Depends
from pathlib import Path
from datetime import datetime
import json

from auth import get_current_user

SAVES_BASE = Path(__file__).parent.parent.parent / "saves"
SAVES_BASE.mkdir(exist_ok=True)

router = APIRouter(prefix="/api/saves")


def _user_dir(user_id: str) -> Path:
    # user_id는 UUID 형식이므로 디렉토리명으로 안전
    d = SAVES_BASE / user_id
    d.mkdir(exist_ok=True)
    return d


def _safe_path(user_id: str, filename: str) -> Path:
    # 경로 탐색 공격 방지: 슬래시·점 시작 불허, .json 확장자만 허용
    if not re.fullmatch(r"[\w\-]+\.json", filename):
        raise HTTPException(status_code=400, detail="잘못된 파일명입니다.")
    path = _user_dir(user_id) / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="저장 파일을 찾을 수 없습니다.")
    return path


@router.get("")
def list_saves(user: dict = Depends(get_current_user)):
    saves = []
    for f in sorted(_user_dir(user["user_id"]).glob("*.json"),
                    key=lambda x: x.stat().st_mtime, reverse=True):
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
async def create_save(req: Request, user: dict = Depends(get_current_user)):
    data        = await req.json()
    scenario_id = re.sub(r"[^\w\-]", "_", data.get("scenarioId", "unknown"))
    chapter     = data.get("progress", {}).get("chapter", 1)
    ts          = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename    = f"{scenario_id}_ch{chapter}_{ts}.json"
    (_user_dir(user["user_id"]) / filename).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"filename": filename}


@router.get("/{filename}")
def get_save(filename: str, user: dict = Depends(get_current_user)):
    return json.loads(_safe_path(user["user_id"], filename).read_text(encoding="utf-8"))


@router.delete("/{filename}")
def delete_save(filename: str, user: dict = Depends(get_current_user)):
    _safe_path(user["user_id"], filename).unlink()
    return {"ok": True}
