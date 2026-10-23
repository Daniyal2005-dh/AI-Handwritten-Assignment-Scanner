"""Processing pipeline: upload photo → enhanced page → lines → text → DB.

Runs inside FastAPI ``BackgroundTasks`` worker threads, one page at a time,
so the HTTP request that starts processing returns immediately and the
frontend polls for status.
"""

from __future__ import annotations

import json
import time

import cv2

from backend.database import get_engine
from backend.models import Assignment, Page

from . import layout, preprocessing, recognition


def _session():
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(
        bind=get_engine(), autoflush=False, expire_on_commit=False, future=True
    )()


def run_page(page_id: int) -> None:
    """Enhance, segment and recognise a single page, then persist results."""
    db = _session()
    try:
        page = db.get(Page, page_id)
        if page is None:
            return
        from backend.config import settings

        settings.ensure_dirs()
        page.status = "processing"
        page.error = None
        db.commit()

        source = settings.storage_dir / page.filename
        bgr = cv2.imread(str(source))
        if bgr is None:
            raise ValueError(f"Could not read image file: {page.filename}")

        started = time.perf_counter()
        result = preprocessing.preprocess_page(
            bgr, max_width=settings.processed_width
        )

        processed_name = f"processed/page_{page.id}.png"
        cv2.imwrite(str(settings.processed_dir / f"page_{page.id}.png"), result.processed)

        boxes = layout.find_line_boxes(result.processed)
        paragraphs = layout.group_paragraphs(
            boxes,
            gap_factor=settings.paragraph_gap_factor,
            heading_height_factor=settings.heading_height_factor,
        )

        recognizer = recognition.get_recognizer()
        lines: list[dict] = []
        for i, box in enumerate(boxes):
            x, y, w, h = box["bbox"]
            h_img, w_img = result.processed.shape[:2]
            x0, y0 = max(0, x), max(0, y)
            crop = result.processed[y0 : min(h_img, y + h), x0 : min(w_img, x + w)]
            rec = recognizer.recognize(crop, index=i)
            lines.append(
                {
                    "i": i,
                    "text": rec.text,
                    "confidence": rec.confidence,
                    "bbox": box["bbox"],
                }
            )

        recognized_text = layout.assemble_text(lines, paragraphs)
        scores = [l["confidence"] for l in lines if l["text"].strip()]

        page.processed_path = processed_name
        page.width, page.height = result.processed.shape[1], result.processed.shape[0]
        page.lines_json = json.dumps(lines, ensure_ascii=False)
        page.paragraphs_json = json.dumps(paragraphs, ensure_ascii=False)
        page.recognized_text = recognized_text
        page.status = "done"
        page.mean_confidence = round(sum(scores) / len(scores), 3) if scores else None
        page.processing_ms = int((time.perf_counter() - started) * 1000)
        db.commit()
    except Exception as exc:  # keep the pipeline alive; surface the error
        db.rollback()
        page = db.get(Page, page_id)
        if page is not None:
            page.status = "error"
            page.error = f"{type(exc).__name__}: {exc}"
            db.commit()
    finally:
        db.close()


def process_assignment(assignment_id: int) -> None:
    """Process every pending page of an assignment in reading order."""
    db = _session()
    try:
        page_ids = [
            p.id
            for p in db.query(Page)
            .filter(Page.assignment_id == assignment_id, Page.status == "pending")
            .order_by(Page.index)
            .all()
        ]
    finally:
        db.close()
    for page_id in page_ids:
        run_page(page_id)
