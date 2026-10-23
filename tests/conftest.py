"""Shared test fixtures: redirect storage to a temp dir and force mock mode."""

from __future__ import annotations

import os

os.environ["SCANNER_RECOGNIZER"] = "mock"

import pytest

from backend import config, database


@pytest.fixture()
def temp_settings(tmp_path, monkeypatch):
    """Point every setting at a fresh temporary directory."""
    monkeypatch.setattr(
        config.settings, "storage_dir", tmp_path / "data", raising=False
    )
    monkeypatch.setattr(
        config.settings, "db_path", tmp_path / "data" / "scanner.db", raising=False
    )
    database.reset_engine()
    config.settings.ensure_dirs()
    yield config.settings
    database.reset_engine()


@pytest.fixture()
def db_session(temp_settings):
    """A real session over an initialised temporary database."""
    from sqlalchemy.orm import sessionmaker

    database.init_db()
    Session = sessionmaker(
        bind=database.get_engine(), autoflush=False, expire_on_commit=False, future=True
    )
    db = Session()
    yield db
    db.close()


def make_test_page_bars(count: int = 5, width: int = 600, height: int = 800) -> bytes:
    """A synthetic page image containing `count` line-like dark bars,
    suitable for exercising segmentation + the mock recognizer."""
    import io

    import cv2
    import numpy as np

    img = np.full((height, width), 245, dtype=np.uint8)
    y = 80
    for i in range(count):
        bar_height = 26
        cv2.rectangle(img, (60, y), (width - 60 - (i % 3) * 90, y + bar_height), 40, -1)
        y += 70 + i * 8
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()
