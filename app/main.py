"""FastAPI app: the HTTP surface over the core pipeline.

Route shape:
  POST   /api/sessions                                  upload a CSV, get themes + opportunities
  GET    /api/sessions/{session_id}                      re-fetch current state
  PATCH  /api/sessions/{session_id}/themes/{theme_id}     rename a theme
  POST   /api/sessions/{session_id}/opportunities/{id}/priority   set priority + notes
  GET    /api/sessions/{session_id}/brief                 export the decision brief
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.clustering import cluster_feedback
from app.export import render_brief_json, render_brief_markdown
from app.ingest import IngestError, parse_feedback_csv
from app.models import DecisionBrief, Priority, VALID_PRIORITIES
from app.priorities import InvalidPriority, OpportunityNotFound, set_priority
from app.store import SessionNotFound, ThemeNotFound, store

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB — an MVP ceiling, not a streaming guard.
ALLOWED_EXTENSIONS = (".csv",)

app = FastAPI(title="Feedback-to-Priorities Copilot", version="0.1.0")

if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


# ---------------------------------------------------------------------------
# Request/response schemas
# ---------------------------------------------------------------------------


class ThemeRenameRequest(BaseModel):
    label: str = Field(min_length=1, max_length=120)


class PriorityRequest(BaseModel):
    priority: Priority
    notes: str = Field(default="", max_length=2000)


# ---------------------------------------------------------------------------
# Serialization helpers (dataclasses -> plain dicts)
# ---------------------------------------------------------------------------


def _theme_dict(theme) -> dict:
    return {
        "id": theme.id,
        "label": theme.label,
        "keywords": theme.keywords,
        "count": theme.count,
        "item_ids": theme.item_ids,
    }


def _evidence_dict(evidence) -> dict:
    return {"item_id": evidence.item_id, "quote": evidence.quote, "source_row": evidence.source_row}


def _opportunity_dict(opportunity) -> dict:
    return {
        "id": opportunity.id,
        "theme_id": opportunity.theme_id,
        "title": opportunity.title,
        "priority": opportunity.priority,
        "notes": opportunity.notes,
        "count": opportunity.count,
        "supporting_evidence": [_evidence_dict(e) for e in opportunity.supporting_evidence],
        "conflicting_evidence": [_evidence_dict(e) for e in opportunity.conflicting_evidence],
    }


def _session_dict(session) -> dict:
    return {
        "session_id": session.id,
        "created_at": session.created_at,
        "total_feedback_items": len(session.items),
        "themes": [_theme_dict(t) for t in session.themes],
        "opportunities": [_opportunity_dict(o) for o in session.opportunities],
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/")
def index() -> FileResponse:
    index_path = WEB_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not built.")
    return FileResponse(str(index_path))


@app.post("/api/sessions", status_code=201)
async def create_session(file: UploadFile) -> JSONResponse:
    filename = (file.filename or "").lower()
    if not filename.endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")

    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is larger than the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
        )

    try:
        items = parse_feedback_csv(raw)
    except IngestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    themes = cluster_feedback(items)
    session = store.create(items, themes)
    return JSONResponse(status_code=201, content=_session_dict(session))


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    try:
        session = store.get(session_id)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="Session not found.") from exc
    return _session_dict(session)


@app.patch("/api/sessions/{session_id}/themes/{theme_id}")
def rename_theme(session_id: str, theme_id: str, body: ThemeRenameRequest) -> dict:
    try:
        store.rename_theme(session_id, theme_id, body.label)
        session = store.get(session_id)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="Session not found.") from exc
    except ThemeNotFound as exc:
        raise HTTPException(status_code=404, detail="Theme not found.") from exc
    return _session_dict(session)


@app.post("/api/sessions/{session_id}/opportunities/{opportunity_id}/priority")
def set_opportunity_priority(session_id: str, opportunity_id: str, body: PriorityRequest) -> dict:
    try:
        session = store.get(session_id)
        set_priority(session.opportunities, opportunity_id, body.priority, body.notes)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="Session not found.") from exc
    except OpportunityNotFound as exc:
        raise HTTPException(status_code=404, detail="Opportunity not found.") from exc
    except InvalidPriority as exc:  # pragma: no cover — Pydantic's Literal check on
        # `PriorityRequest.priority` already rejects anything outside VALID_PRIORITIES
        # before this code runs; kept as defense-in-depth if that ever changes.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _session_dict(session)


@app.get("/api/sessions/{session_id}/brief")
def get_brief(session_id: str, format: str = "markdown"):
    try:
        session = store.get(session_id)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="Session not found.") from exc

    brief = DecisionBrief(
        session_id=session.id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_feedback_items=len(session.items),
        opportunities=session.opportunities,
    )

    if format == "json":
        return JSONResponse(content=render_brief_json(brief))
    if format == "markdown":
        return PlainTextResponse(content=render_brief_markdown(brief), media_type="text/markdown")
    raise HTTPException(status_code=400, detail="format must be 'markdown' or 'json'.")
