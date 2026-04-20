"""
routers/scenarios.py — 시나리오 조회 API
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from scenarios_loader import SCENARIOS, SCENARIOS_DIR

router = APIRouter(prefix="/api/scenarios")


@router.get("")
def list_scenarios():
    return SCENARIOS


@router.get("/{scenario_id}")
def get_scenario(scenario_id: str):
    scenario = next((s for s in SCENARIOS if s["id"] == scenario_id), None)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"시나리오 '{scenario_id}'를 찾을 수 없습니다.")
    return scenario


@router.get("/{scenario_id}/map-image")
def get_map_image(scenario_id: str):
    scenario_dir = SCENARIOS_DIR / scenario_id
    for ext in ("png", "jpg", "jpeg", "webp"):
        path = scenario_dir / f"map.{ext}"
        if path.exists():
            return FileResponse(path, media_type=f"image/{ext}")
    raise HTTPException(status_code=404, detail=f"시나리오 '{scenario_id}'의 지도 이미지가 없습니다.")
