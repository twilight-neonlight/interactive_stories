"""
backend/auth.py — JWT 유틸리티 + 사용자 관리
"""

import json, uuid, re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import SECRET_KEY, GOOGLE_CLIENT_ID

ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 30

bearer_scheme = HTTPBearer()

USERS_FILE = Path(__file__).parent / "data" / "users.json"

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


# ── 파일 I/O ──────────────────────────────────────────────────────────────────

def _load_users() -> dict:
    if not USERS_FILE.exists():
        return {}
    return json.loads(USERS_FILE.read_text(encoding="utf-8"))


def _save_users(users: dict):
    USERS_FILE.parent.mkdir(exist_ok=True)
    USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 게스트 (UUID) ──────────────────────────────────────────────────────────────

def get_or_create_guest(guest_uuid: str) -> dict:
    normalized = guest_uuid.strip().lower()
    if not _UUID_RE.match(normalized):
        raise ValueError("유효하지 않은 UUID입니다.")

    users = _load_users()
    for user_id, user in users.items():
        if user.get("type") == "guest" and user.get("guest_uuid") == normalized:
            return {"user_id": user_id, "username": user["username"]}

    user_id = str(uuid.uuid4())
    username = f"게스트_{normalized[:8]}"
    users[user_id] = {"type": "guest", "username": username, "guest_uuid": normalized}
    _save_users(users)
    return {"user_id": user_id, "username": username}


# ── 구글 OAuth ────────────────────────────────────────────────────────────────

async def verify_google_token(id_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": id_token},
            timeout=10,
        )
    if r.status_code != 200:
        raise ValueError("유효하지 않은 Google 토큰입니다.")

    data = r.json()
    if GOOGLE_CLIENT_ID and data.get("aud") != GOOGLE_CLIENT_ID:
        raise ValueError("토큰의 대상 앱이 일치하지 않습니다.")

    return {
        "google_id": data["sub"],
        "email": data.get("email", ""),
        "name": data.get("name", ""),
    }


def get_or_create_google_user(google_id: str, email: str, name: str) -> dict:
    users = _load_users()
    for user_id, user in users.items():
        if user.get("type") == "google" and user.get("google_id") == google_id:
            return {"user_id": user_id, "username": user["username"]}

    user_id = str(uuid.uuid4())
    username = name or (email.split("@")[0] if email else "Google User")
    users[user_id] = {
        "type": "google",
        "username": username,
        "google_id": google_id,
        "email": email,
    }
    _save_users(users)
    return {"user_id": user_id, "username": username}


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(user_id: str, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": user_id, "username": username, "exp": expire},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub", "")
        if not user_id:
            raise JWTError
        return {"user_id": user_id, "username": payload.get("username", "")}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 토큰이 유효하지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
