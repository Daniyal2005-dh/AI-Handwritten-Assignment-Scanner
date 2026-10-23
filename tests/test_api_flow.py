"""End-to-end API flow with the mock recognizer (fast, offline)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_test_page_bars


@pytest.fixture()
def client(temp_settings):
    from backend.app import app

    with TestClient(app) as c:  # startup runs: ensure dirs, create tables
        yield c


def test_full_assignment_flow(client):
    # --- create with three pages ---------------------------------------
    files = [
        ("files", (f"page{i}.png", make_test_page_bars(), "image/png")) for i in (1, 2, 3)
    ]
    res = client.post(
        "/api/assignments",
        data={"name": "Assignment 2", "subject": "Digital Logic"},
        files=files,
    )
    assert res.status_code == 201, res.text
    aid = res.json()["id"]
    assert len(res.json()["pages"]) == 3

    # Background tasks ran synchronously under TestClient → all pages done.
    detail = client.get(f"/api/assignments/{aid}").json()
    statuses = [p["status"] for p in detail["pages"]]
    assert statuses == ["done", "done", "done"], statuses
    assert detail["status_counts"]["done"] == 3

    # --- page detail -----------------------------------------------------
    page_id = detail["pages"][0]["id"]
    page = client.get(f"/api/pages/{page_id}").json()
    assert page["status"] == "done"
    assert len(page["lines"]) > 0
    assert "(mock recognition)" in page["text"]
    assert page["mean_confidence"] is not None

    # --- images ----------------------------------------------------------
    for variant in ("original", "processed", "boxes"):
        res = client.get(f"/api/pages/{page_id}/image?variant={variant}&boxes=1")
        assert res.status_code == 200
        assert res.headers["content-type"] == "image/png"

    # --- text correction ---------------------------------------------------
    res = client.put(
        f"/api/pages/{page_id}/text",
        json={"text": "Name: Daniyal\n\nCorrected by a human."},
    )
    assert res.json()["corrected_text"] == "Name: Daniyal\n\nCorrected by a human."

    # --- exports -------------------------------------------------------------
    res = client.get(f"/api/assignments/{aid}/export?kind=txt")
    assert res.status_code == 200
    assert "Corrected by a human." in res.text

    res = client.get(f"/api/assignments/{aid}/export?kind=original_pdf")
    assert res.status_code == 200
    assert res.content[:5] == b"%PDF-"

    res = client.get(f"/api/assignments/{aid}/export?kind=searchable_pdf")
    assert res.content[:5] == b"%PDF-"
    from io import BytesIO

    from pypdf import PdfReader

    reader = PdfReader(BytesIO(res.content))
    assert len(reader.pages) == 3
    assert "(mock recognition)" in reader.pages[0].extract_text()

    res = client.get(f"/api/assignments/{aid}/export?kind=docx")
    assert res.content[:2] == b"PK"

    # unknown kind → 400
    assert client.get(f"/api/assignments/{aid}/export?kind=nope").status_code == 400

    # --- dashboard list & rename ------------------------------------------
    listing = client.get("/api/assignments", params={"subject": "Digital Logic"}).json()
    assert any(a["id"] == aid for a in listing)

    res = client.patch(f"/api/assignments/{aid}", json={"name": "Assignment 2 edited"})
    assert res.json()["name"] == "Assignment 2 edited"

    # --- add pages ----------------------------------------------------------
    res = client.post(
        f"/api/assignments/{aid}/add_pages",
        files=[("files", ("page4.png", make_test_page_bars(), "image/png"))],
    )
    assert res.status_code == 201
    assert len(res.json()["pages"]) == 4

    # --- status endpoint ------------------------------------------------------
    status = client.get("/api/status").json()
    assert status["recognizer"] == "mock"

    # --- delete ---------------------------------------------------------------
    assert client.delete(f"/api/assignments/{aid}").json()["ok"] is True
    assert client.get(f"/api/assignments/{aid}").status_code == 404
    assert client.get(f"/api/pages/{page_id}").status_code == 404


def test_upload_validation(client):
    res = client.post(
        "/api/assignments",
        data={"name": "Bad file"},
        files=[("files", ("page.txt", b"not an image", "text/plain"))],
    )
    assert res.status_code == 400

    res = client.post("/api/assignments", data={"name": ""}, files=[])
    assert res.status_code in (400, 422)


def test_404s(client):
    assert client.get("/api/assignments/999").status_code == 404
    assert client.get("/api/pages/999").status_code == 404
