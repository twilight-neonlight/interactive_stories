"""
backend/main.py — FastAPI 서버 진입점
실행: uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from routers.scenarios    import router as scenarios_router
from routers.saves        import router as saves_router
from routers.game         import router as game_router
from routers.auth         import router as auth_router
from routers.quick_battle import router as quick_battle_router
from routers.client_config import router as config_router

_NO_CACHE_EXTS = ('.js', '.css', '.html')

class _NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path.split('?')[0]
        if path.endswith(_NO_CACHE_EXTS):
            response.headers['Cache-Control'] = 'no-cache'
        return response

app = FastAPI(title="Interactive Stories API")
app.add_middleware(_NoCacheMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(config_router)
app.include_router(scenarios_router)
app.include_router(saves_router)
app.include_router(game_router)
app.include_router(quick_battle_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return RedirectResponse(url="/frontend/main_menu.html")


# static 서빙 범위를 공개 디렉터리로 제한
# backend/ (API 키, 사용자 데이터) 와 saves/ (세이브 파일) 는 절대 포함하지 않는다
_ROOT_DIR = Path(__file__).parent.parent
app.mount("/frontend", StaticFiles(directory=str(_ROOT_DIR / "frontend")), name="frontend")
app.mount("/state",    StaticFiles(directory=str(_ROOT_DIR / "state")),    name="state")
app.mount("/tools",    StaticFiles(directory=str(_ROOT_DIR / "tools")),    name="tools")
