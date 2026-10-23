"""ORM models: Assignment (dashboard record) and Page (one scanned sheet)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    DateTime,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    subject: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    pages: Mapped[list["Page"]] = relationship(
        back_populates="assignment",
        cascade="all, delete-orphan",
        order_by="Page.index",
    )

    @property
    def status_counts(self) -> dict[str, int]:
        counts = {"pending": 0, "processing": 0, "done": 0, "error": 0}
        for p in self.pages:
            counts[p.status] = counts.get(p.status, 0) + 1
        return counts


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"), index=True
    )
    index: Mapped[int] = mapped_column(Integer)  # 1-based reading order

    # Path (relative to config.settings.storage_dir) of the uploaded photo.
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    # Path of the enhanced image produced by preprocessing (absent until done).
    processed_path: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    # pending | processing | done | error
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Recognition results
    lines_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    paragraphs_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recognized_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    corrected_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mean_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    processing_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    assignment: Mapped["Assignment"] = relationship(back_populates="pages")

    # ------------------------------------------------------------------ #
    # Convenience accessors

    def lines(self) -> list[dict[str, Any]]:
        return json.loads(self.lines_json) if self.lines_json else []

    def paragraphs(self) -> list[dict[str, Any]]:
        return json.loads(self.paragraphs_json) if self.paragraphs_json else []

    @property
    def text(self) -> str:
        """Text used everywhere: user corrections win over raw recognition."""
        return self.corrected_text or self.recognized_text or ""

    def absolute_filename(self, storage_dir) -> "Path":
        from pathlib import Path

        return Path(storage_dir) / self.filename

    @property
    def image_array(self):
        """Best available page image (enhanced version preferred), grayscale."""
        import cv2
        from pathlib import Path

        from backend.config import settings

        rel = self.processed_path or self.filename
        return cv2.imread(str(Path(settings.storage_dir) / rel), cv2.IMREAD_GRAYSCALE)
