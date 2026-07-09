"""FastAPI app factory for the Chatty web API."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.skills_manager import SkillsManager
from src.web import config, state
from src.web.routers import (
    audio,
    chat_media,
    chat_ws,
    code_browser,
    gmail,
    health,
    insights,
    media,
    memory_wiki,
    notes,
    reminders,
    requests as requests_router,
    sessions,
    system,
    taste_audit,
    transcriptions,
    trending,
    video_production,
    watchlist,
    webcam,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.skills_manager = SkillsManager()
    await state.skills_manager.load_skills()
    print(f"[chatty-web] Loaded {len(state.skills_manager.skills)} skills")
    print(f"[chatty-web] Listening on port {config.PORT}")
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Chatty Web API", version="1.0.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for router_module in (
        health, notes, transcriptions, audio, media, chat_media, watchlist, insights,
        reminders, requests_router, video_production, trending, webcam, memory_wiki,
        code_browser, system, gmail, sessions, chat_ws, taste_audit,
    ):
        app.include_router(router_module.router)

    return app
