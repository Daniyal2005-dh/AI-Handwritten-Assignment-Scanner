"""Export builders: validate every output format end to end."""

from __future__ import annotations

import json

import pytest

from backend.models import Assignment, Page
from backend.services import exports


def make_page(db, assignment, index, tmp_path, with_lines=True) -> Page:
    import cv2
    import numpy as np

    image = np.full((900, 636), 230, dtype=np.uint8)
    path = tmp_path / f"page_{index}.png"
    cv2.imwrite(str(path), image)
    rel = str(path)
    page = Page(
        assignment_id=assignment.id,
        index=index,
        filename=rel,
        processed_path=rel,
        status="done",
    )
    if with_lines:
        lines = [
            {"i": 0, "text": "Heading line", "confidence": 0.9, "bbox": [50, 60, 500, 60]},
            {"i": 1, "text": "Body text one", "confidence": 0.8, "bbox": [50, 220, 500, 40]},
        ]
        page.lines_json = json.dumps(lines)
        page.paragraphs_json = json.dumps(
            [
                {"lines": [0], "heading": True},
                {"lines": [1], "heading": False},
            ]
        )
        page.recognized_text = "Heading line\n\nBody text one"
    db.add(page)
    db.commit()
    db.refresh(page)
    return page


@pytest.fixture()
def seeded(db_session):
    assignment = Assignment(name="Test Assignment", subject="Digital Logic")
    db_session.add(assignment)
    db_session.commit()
    return assignment


def test_txt_export_contains_text(seeded, db_session, tmp_path):
    make_page(db_session, seeded, 1, tmp_path)
    data = exports.export_txt(seeded, seeded.pages).decode("utf-8")
    assert "Assigned" in data or "Test Assignment" in data
    assert "Body text one" in data


def test_docx_export_valid_zip(seeded, db_session, tmp_path):
    make_page(db_session, seeded, 1, tmp_path)
    blob = exports.export_docx(seeded, seeded.pages)
    from docx import Document
    from io import BytesIO

    doc = Document(BytesIO(blob))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Test Assignment" in text
    assert "Page 1" in text
    assert "Body text one" in text


def test_original_pdf_valid(seeded, db_session, tmp_path):
    make_page(db_session, seeded, 1, tmp_path)
    blob = exports.export_original_pdf(seeded, seeded.pages)
    assert blob[:5] == b"%PDF-"


def test_searchable_pdf_after_correction(seeded, db_session, tmp_path):
    page = make_page(db_session, seeded, 1, tmp_path)
    page.corrected_text = "Heading line\n\nCorrected sentence"
    db_session.commit()

    blob = exports.export_searchable_pdf(seeded, seeded.pages)
    assert blob[:5] == b"%PDF-"

    from pypdf import PdfReader
    from io import BytesIO

    reader = PdfReader(BytesIO(blob))
    assert len(reader.pages) == 1
    extracted = reader.pages[0].extract_text()
    assert "Body text one" in extracted  # line layer stays aligned to lines


def test_slug_is_safe(seeded):
    seeded.name = "Assignment/2: *scan*"
    slug = exports._slug(seeded.name)
    assert "/" not in slug and "*" not in slug
