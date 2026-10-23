"""FastAPI application wiring: static frontend + JSON API."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.database import init_db

from .routers import assignments, pages

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def fix_stuck_pages() -> None:
    """After a restart, pages that were mid-processing are re-queued."""
    from sqlalchemy import update

    from backend.database import get_engine
    from backend.models import Page

    with get_engine().begin() as conn:
        conn.execute(
            update(Page).where(Page.status == "processing").values(status="pending")
        )


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Handwritten Assignment Scanner",
        description="Photo → enhanced page → text lines → editable text → PDF/DOCX exports",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(assignments.router)
    app.include_router(pages.router)

    @app.get("/api/status", tags=["system"])
    def status():
        import backend.services.recognition as rec

        provider = rec.get_recognizer()
        device = "n/a (mock)" if provider.name == "mock" else settings.device
        return {
            "recognizer": provider.name,
            "device": device,
            "trocr_model": settings.trocr_model if provider.name == "trocr" else None,
            "hint": (
                "Mock mode active. Set SCANNER_RECOGNIZER=trocr and restart "
                "for real handwriting recognition."
                if provider.name == "mock"
                else "TrOCR model loaded."
            ),
        }

    @app.on_event("startup")
    def on_startup() -> None:
        settings.ensure_dirs()
        init_db()
        fix_stuck_pages()

    # Static frontend last, so API routes and /docs win.
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    return app


app = create_app()
