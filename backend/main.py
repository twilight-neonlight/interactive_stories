"""
backend/main.py — FastAPI 서버 진입점
실행: uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from routers.scenarios    import router as scenarios_router
from routers.saves        import router as saves_router
from routers.game         import router as game_router
from routers.auth         import router as auth_router
from routers.quick_battle import router as quick_battle_router

app = FastAPI(title="Interactive Stories API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

app.include_router(auth_router)
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


_ROOT_DIR = Path(__file__).parent.parent
app.mount("/", StaticFiles(directory=str(_ROOT_DIR), html=True), name="static")
