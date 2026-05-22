"""
routers/auth.py — 인증 API (게스트, 구글)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import GOOGLE_CLIENT_ID, INVITE_CODE
from auth import (
    create_access_token,
    get_or_create_guest, verify_google_token, get_or_create_google_user,
)

router = APIRouter(prefix="/api/auth")


def _check_invite(code: str):
    if INVITE_CODE and code != INVITE_CODE:
        raise HTTPException(status_code=403, detail="초대 코드가 올바르지 않습니다.")


class GuestRequest(BaseModel):
    uuid: str
    invite_code: str = ""


class GoogleRequest(BaseModel):
    id_token: str
    invite_code: str = ""


@router.get("/config")
def get_auth_config():
    return {"google_client_id": GOOGLE_CLIENT_ID, "invite_required": bool(INVITE_CODE)}


@router.post("/guest")
def guest_login(req: GuestRequest):
    _check_invite(req.invite_code)
    try:
        user = get_or_create_guest(req.uuid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"token": create_access_token(user["user_id"], user["username"]), "username": user["username"]}


@router.post("/google")
async def google_login(req: GoogleRequest):
    _check_invite(req.invite_code)
    try:
        info = await verify_google_token(req.id_token)
        user = get_or_create_google_user(info["google_id"], info["email"], info["name"])
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return {"token": create_access_token(user["user_id"], user["username"]), "username": user["username"]}
