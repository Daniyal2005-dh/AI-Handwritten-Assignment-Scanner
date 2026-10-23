"""Page endpoints: detail, image with optional line-box overlay,
text correction and reprocessing."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models import Page

from . import serializers

router = APIRouter(prefix="/api/pages", tags=["pages"])


class TextUpdate(BaseModel):
    text: str


def _get_page_or_404(db: Session, page_id: int) -> Page:
    page = db.get(Page, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


@router.get("/{page_id}")
def get_page(page_id: int, db: Session = Depends(get_db)):
    page = _get_page_or_404(db, page_id)
    return serializers.page_detail(page)


@router.get("/{page_id}/image")
def get_page_image(
    page_id: int,
    variant: str = Query("processed", description="original | processed"),
    boxes: bool = Query(False, description="Draw detected line boxes on the image"),
    db: Session = Depends(get_db),
):
    import cv2

    page = _get_page_or_404(db, page_id)
    if variant == "processed" and page.processed_path:
        img = cv2.imread(str(settings.storage_dir / page.processed_path), cv2.IMREAD_GRAYSCALE)
    elif variant == "original":
        img = cv2.imread(str(settings.storage_dir / page.filename), cv2.IMREAD_GRAYSCALE)
    else:
        raise HTTPException(status_code=400, detail="Unknown variant or image not ready")
    if img is None:
        raise HTTPException(status_code=404, detail="Image file missing")

    if boxes and page.lines_json:
        overlay = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        for line in page.lines():
            x, y, w, h = line["bbox"]
            colour = (30, 30, 220)
            cv2.rectangle(overlay, (x, y), (x + w, y + h), colour, 3)

        # Encode with clean compression parameters.
        ok, buf = cv2.imencode(".png", overlay, [cv2.IMWRITE_PNG_COMPRESSION, 3])
        if ok:
            return Response(content=buf.tobytes(), media_type="image/png")
        raise HTTPException(status_code=500, detail="Image encoding failed")

    ok, buf = cv2.imencode(".png", img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), [cv2.IMWRITE_PNG_COMPRESSION, 3])
    if not ok:
        raise HTTPException(status_code=500, detail="Image encoding failed")
    return Response(content=buf.tobytes(), media_type="image/png")


@router.put("/{page_id}/text")
def update_page_text(page_id: int, payload: TextUpdate, db: Session = Depends(get_db)):
    page = _get_page_or_404(db, page_id)
    page.corrected_text = payload.text
    db.commit()
    db.refresh(page)
    return serializers.page_detail(page)


@router.post("/{page_id}/reprocess")
def reprocess_page(page_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    page = _get_page_or_404(db, page_id)
    page.status = "pending"
    page.error = None
    page.processed_path = None
    page.lines_json = None
    page.paragraphs_json = None
    page.recognized_text = None
    page.mean_confidence = None
    page.processing_ms = None
    db.commit()
    background_tasks.add_task(_run_page, page_id)
    return {"ok": True, "page_id": page_id, "status": "pending"}


def _run_page(page_id: int) -> None:
    from backend.services import pipeline

    pipeline.run_page(page_id)
