"""Serialisation helpers building stable API payloads."""

from __future__ import annotations

from typing import Any


def page_summary(page) -> dict[str, Any]:
    return {
        "id": page.id,
        "index": page.index,
        "status": page.status,
        "error": page.error,
        "original_url": f"/api/pages/{page.id}/image?variant=original",
        "processed_url": (
            f"/api/pages/{page.id}/image?variant=processed"
            if page.processed_path
            else None
        ),
        "boxes_url": (
            f"/api/pages/{page.id}/image?variant=processed&boxes=1"
            if page.processed_path and page.lines_json
            else None
        ),
        "mean_confidence": page.mean_confidence,
        "processing_ms": page.processing_ms,
        "updated_at": page.updated_at.isoformat() if page.updated_at else None,
    }


def page_detail(page) -> dict[str, Any]:
    from backend.config import settings

    lines = page.lines()
    low_confidence = [
        {"i": l["i"], "confidence": l["confidence"], "text": l["text"]}
        for l in lines
        if l.get("text", "").strip() and l["confidence"] < settings.min_confidence
    ]
    return {
        "id": page.id,
        "assignment_id": page.assignment_id,
        "index": page.index,
        "status": page.status,
        "error": page.error,
        "width": page.width,
        "height": page.height,
        "lines": lines,
        "paragraphs": page.paragraphs(),
        "recognized_text": page.recognized_text or "",
        "corrected_text": page.corrected_text,
        "text": page.text,
        "mean_confidence": page.mean_confidence,
        "processing_ms": page.processing_ms,
        "low_confidence": low_confidence,
        "original_url": f"/api/pages/{page.id}/image?variant=original",
        "processed_url": (
            f"/api/pages/{page.id}/image?variant=processed" if page.processed_path else None
        ),
        "boxes_url": (
            f"/api/pages/{page.id}/image?variant=processed&boxes=1"
            if page.processed_path and page.lines_json
            else None
        ),
        "updated_at": page.updated_at.isoformat() if page.updated_at else None,
    }


def assignment_summary(assignment) -> dict[str, Any]:
    counts = assignment.status_counts
    return {
        "id": assignment.id,
        "name": assignment.name,
        "subject": assignment.subject,
        "page_count": len(assignment.pages),
        "status_counts": counts,
        "created_at": assignment.created_at.isoformat() if assignment.created_at else None,
    }


def assignment_detail(assignment) -> dict[str, Any]:
    return {
        **assignment_summary(assignment),
        "pages": [page_summary(p) for p in assignment.pages],
    }
