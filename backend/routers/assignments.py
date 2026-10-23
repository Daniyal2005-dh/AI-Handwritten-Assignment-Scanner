"""Assignment endpoints: create with uploads, dashboard list/detail,
rename, delete, and the export API (Step 5)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models import Assignment, Page
from backend.services import exports

from . import serializers

router = APIRouter(prefix="/api/assignments", tags=["assignments"])


class AssignmentUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None


def _get_assignment_or_404(db: Session, assignment_id: int) -> Assignment:
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return assignment


@router.post("", status_code=201)
async def create_assignment(
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    subject: str = Form(""),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Create an assignment from one or more page photos and start processing."""
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Assignment name is required")
    if not files:
        raise HTTPException(status_code=400, detail="At least one page image is required")

    settings.ensure_dirs()
    assignment = Assignment(name=name[:120], subject=(subject or "").strip()[:80])
    db.add(assignment)
    db.flush()

    assignment_dir = settings.uploads_dir / str(assignment.id)
    assignment_dir.mkdir(parents=True, exist_ok=True)

    max_bytes = settings.max_upload_mb * 1024 * 1024
    for i, upload in enumerate(files, start=1):
        ext = Path(upload.filename or "").suffix.lower()
        if ext not in settings.allowed_ext:
            raise HTTPException(
                status_code=400,
                detail=f"'{upload.filename}': unsupported file type. Allowed: {', '.join(settings.allowed_ext)}",
            )
        content = await upload.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail=f"'{upload.filename}' is empty")
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"'{upload.filename}' exceeds the {settings.max_upload_mb} MB page limit",
            )
        page = Page(
            assignment_id=assignment.id,
            index=i,
            filename=f"uploads/{assignment.id}/page_{i}{ext}",
        )
        (settings.storage_dir / page.filename).write_bytes(content)
        db.add(page)

    db.commit()
    background_tasks.add_task(_run_assignment, assignment.id)
    db.refresh(assignment)
    return serializers.assignment_detail(assignment)


def _run_assignment(assignment_id: int) -> None:
    from backend.services import pipeline

    pipeline.process_assignment(assignment_id)


@router.post("/{assignment_id}/add_pages", status_code=201)
async def add_pages(
    assignment_id: int,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Append more page photographs to an existing assignment."""
    assignment = _get_assignment_or_404(db, assignment_id)
    if not files:
        raise HTTPException(status_code=400, detail="At least one page image is required")

    settings.ensure_dirs()
    assignment_dir = settings.uploads_dir / str(assignment.id)
    assignment_dir.mkdir(parents=True, exist_ok=True)

    next_index = max((p.index for p in assignment.pages), default=0) + 1
    max_bytes = settings.max_upload_mb * 1024 * 1024
    for upload in files:
        ext = Path(upload.filename or "").suffix.lower()
        if ext not in settings.allowed_ext:
            raise HTTPException(
                status_code=400,
                detail=f"'{upload.filename}': unsupported file type",
            )
        content = await upload.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail=f"'{upload.filename}' is empty")
        if len(content) > max_bytes:
            raise HTTPException(status_code=413, detail=f"'{upload.filename}' is too large")

        page = Page(
            assignment_id=assignment.id,
            index=next_index,
            filename=f"uploads/{assignment.id}/page_{next_index}{ext}",
        )
        next_index += 1
        (settings.storage_dir / page.filename).write_bytes(content)
        db.add(page)

    db.commit()
    background_tasks.add_task(_run_assignment, assignment.id)
    db.refresh(assignment)
    return serializers.assignment_detail(assignment)


@router.get("")
def list_assignments(
    subject: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
):
    stmt = select(Assignment).order_by(Assignment.created_at.desc())
    if subject:
        stmt = stmt.where(Assignment.subject == subject)
    if q:
        stmt = stmt.where(Assignment.name.ilike(f"%{q}%"))
    assignments = db.scalars(stmt).all()
    return [serializers.assignment_summary(a) for a in assignments]


@router.get("/{assignment_id}")
def get_assignment(assignment_id: int, db: Session = Depends(get_db)):
    assignment = _get_assignment_or_404(db, assignment_id)
    return serializers.assignment_detail(assignment)


@router.patch("/{assignment_id}")
def rename_assignment(
    assignment_id: int, payload: AssignmentUpdate, db: Session = Depends(get_db)
):
    assignment = _get_assignment_or_404(db, assignment_id)
    if payload.name is not None and payload.name.strip():
        assignment.name = payload.name.strip()[:120]
    if payload.subject is not None:
        assignment.subject = payload.subject.strip()[:80]
    db.commit()
    db.refresh(assignment)
    return serializers.assignment_detail(assignment)


@router.delete("/{assignment_id}")
def delete_assignment(assignment_id: int, db: Session = Depends(get_db)):
    assignment = _get_assignment_or_404(db, assignment_id)
    page_ids = [p.id for p in assignment.pages]

    db.delete(assignment)
    db.commit()

    # Best-effort cleanup of files that reference this assignment.
    shutil.rmtree(settings.uploads_dir / str(assignment_id), ignore_errors=True)
    for page_id in page_ids:
        (settings.processed_dir / f"page_{page_id}.png").unlink(missing_ok=True)
    return {"ok": True, "deleted_pages": page_ids}


@router.get("/{assignment_id}/export")
def export_assignment(
    assignment_id: int,
    kind: str = Query("searchable_pdf", description="original_pdf | searchable_pdf | docx | txt"),
    db: Session = Depends(get_db),
):
    assignment = _get_assignment_or_404(db, assignment_id)
    spec = exports.EXPORT_KINDS.get(kind)
    if spec is None:
        raise HTTPException(status_code=400, detail=f"Unknown export kind: {kind}")
    content = spec["builder"](assignment, assignment.pages)
    filename = f"{exports._slug(assignment.name)}.{spec['ext']}"
    return Response(
        content=content,
        media_type=spec["media_type"],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
