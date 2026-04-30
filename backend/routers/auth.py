"""
routers/auth.py — 인증 API (게스트, 구글)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import GOOGLE_CLIENT_ID
from auth import (
    create_access_token,
    get_or_create_guest, verify_google_token, get_or_create_google_user,
)

router = APIRouter(prefix="/api/auth")


class GuestRequest(BaseModel):
    uuid: str


class GoogleRequest(BaseModel):
    id_token: str


@router.get("/config")
def get_auth_config():
    return {"google_client_id": GOOGLE_CLIENT_ID}


@router.post("/guest")
def guest_login(req: GuestRequest):
    try:
        user = get_or_create_guest(req.uuid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"token": create_access_token(user["user_id"], user["username"]), "username": user["username"]}


@router.post("/google")
async def google_login(req: GoogleRequest):
    try:
        info = await verify_google_token(req.id_token)
        user = get_or_create_google_user(info["google_id"], info["email"], info["name"])
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return {"token": create_access_token(user["user_id"], user["username"]), "username": user["username"]}
