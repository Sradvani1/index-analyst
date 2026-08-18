"""FastAPI application for the Phase 2 web viewer."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from ..config import get_settings
from ..files import InputError
from .chat_api import router as chat_router
from .models import FrameworkResponse, HealthResponse, RunDetail, RunSummary
from .service import RunNotFoundError, get_framework, get_run, list_runs, podcast_audio_path

app = FastAPI(title="SPX Analyst Viewer", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

if get_settings().chat_enabled:
    app.include_router(chat_router)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/runs", response_model=list[RunSummary])
def api_list_runs() -> list[RunSummary]:
    return list_runs()


@app.get("/api/framework", response_model=FrameworkResponse)
def api_framework() -> FrameworkResponse:
    try:
        return get_framework()
    except (InputError, OSError, UnicodeError) as exc:
        raise HTTPException(status_code=503, detail="framework documents unavailable") from exc


@app.get("/api/runs/{date}", response_model=RunDetail)
def api_get_run(date: str) -> RunDetail:
    try:
        return get_run(date)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/runs/{date}/podcast.mp3")
def api_podcast_audio(date: str) -> FileResponse:
    try:
        path = podcast_audio_path(date)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="podcast audio not found")
    return FileResponse(path, media_type="audio/mpeg")
