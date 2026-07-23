"""FastAPI app factory for the Atlas web API."""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.skills_manager import SkillsManager
from src.managers import blog_writer
from src.web import config, state
from src.web.routers import (
    audio,
    blog,
    chat_media,
    chat_ws,
    code_browser,
    gmail,
    health,
    insights,
    linkedin,
    media,
    memory_wiki,
    notes,
    png_stamp,
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
    whatsapp,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.skills_manager = SkillsManager()
    await state.skills_manager.load_skills()
    print(f"[chatty-web] Loaded {len(state.skills_manager.skills)} skills")
    print(f"[chatty-web] Listening on port {config.PORT}")
    # Autonomous blog writer. Generates review drafts on an interval; no-ops if
    # the blog API token is not configured.
    blog_task = asyncio.create_task(blog_writer.scheduler_loop())
    yield
    blog_task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(title="Atlas Web API", version="1.0.0", lifespan=lifespan)

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
        code_browser, system, gmail, whatsapp, linkedin, sessions, chat_ws, taste_audit,
        png_stamp, blog,
    ):
        app.include_router(router_module.router)

    return app
