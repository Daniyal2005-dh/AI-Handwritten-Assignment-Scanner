"""Central configuration for the AI Assignment Scanner.

Everything is read from environment variables once at import time so the app
is easy to configure (and easy to point at temporary directories in tests).

Environment variables
---------------------
SCANNER_DATA_DIR      root folder for uploads, processed pages and the DB
SCANNER_RECOGNIZER    "mock" (instant placeholder) or "trocr" (real TrOCR AI)
SCANNER_TROCR_MODEL   HF model id (default: microsoft/trocr-base-handwritten)
SCANNER_DEVICE        "cpu", "cuda" or "auto"
SCANNER_MAX_UPLOAD_MB max size of an uploaded image, megabytes
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    storage_dir: Path
    db_path: Path
    recognizer: str = "mock"

    # Recognition model configuration
    trocr_model: str = "microsoft/trocr-base-handwritten"
    device: str = "auto"           # auto | cpu | cuda  (resolved when the model loads)
    cpu_threads: int = 0           # 0 = leave to torch defaults

    # Upload constraints
    max_upload_mb: int = 15
    allowed_ext: tuple[str, ...] = (".jpg", ".jpeg", ".png")

    # Image pipeline tuning
    processed_width: int = 1700    # long edge of the enhanced A4 page
    min_confidence: float = 0.60   # lines below this are flagged for review

    # Layout tuning
    paragraph_gap_factor: float = 1.7
    heading_height_factor: float = 1.35

    @property
    def uploads_dir(self) -> Path:
        return self.storage_dir / "uploads"

    @property
    def processed_dir(self) -> Path:
        return self.storage_dir / "processed"

    @property
    def exports_dir(self) -> Path:
        return self.storage_dir / "exports"

    def ensure_dirs(self) -> None:
        for d in (self.uploads_dir, self.processed_dir, self.exports_dir):
            d.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    base = Path(os.environ.get("SCANNER_DATA_DIR", Path.cwd() / "data")).resolve()
    return Settings(
        storage_dir=base,
        db_path=base / "scanner.db",
        recognizer=os.environ.get("SCANNER_RECOGNIZER", "mock").strip().lower(),
        trocr_model=os.environ.get("SCANNER_TROCR_MODEL", "microsoft/trocr-base-handwritten"),
        device=os.environ.get("SCANNER_DEVICE", "auto").strip().lower(),
        cpu_threads=int(os.environ.get("SCANNER_CPU_THREADS", "0") or 0),
        max_upload_mb=int(os.environ.get("SCANNER_MAX_UPLOAD_MB", "15") or 15),
    )


settings = load_settings()


def reload_settings() -> None:
    """Re-read environment variables and activate the new settings."""
    global settings
    settings = load_settings()
    import backend.database as database

    database.reset_engine()
