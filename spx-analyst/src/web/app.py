"""FastAPI application for the Phase 2 web viewer."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .models import HealthResponse, RunDetail, RunSummary
from .service import RunNotFoundError, get_run, list_runs

app = FastAPI(title="SPX Analyst Viewer", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/runs", response_model=list[RunSummary])
def api_list_runs() -> list[RunSummary]:
    return list_runs()


@app.get("/api/runs/{date}", response_model=RunDetail)
def api_get_run(date: str) -> RunDetail:
    try:
        return get_run(date)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
