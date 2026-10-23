"""Unit tests for the image enhancement pipeline and layout engine."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from backend.services import layout, preprocessing


@pytest.fixture()
def synthetic_photo():
    """A page photo: paper on a dark desk, with shadow, bars of 'text'."""
    page = np.full((1122, 794), 248, dtype=np.uint8)
    for i in range(6):
        cv2.rectangle(page, (80, 100 + i * 90), (700 - i * 40, 132 + i * 90), 30, -1)
    # page curvature / shadow: brighten top-left, darken bottom-right
    h, w = page.shape
    x = np.linspace(1.0, 0.78, w)[None, :]
    y = np.linspace(1.0, 0.88, h)[:, None]
    shaded = np.clip(page.astype(np.float32) * np.minimum(x, y), 0, 255).astype(np.uint8)
    colored = cv2.cvtColor(shaded, cv2.COLOR_GRAY2BGR)

    # place the paper on a dark desk with a visible margin
    env = np.full((h + 60, w + 60), 70, dtype=np.uint8)
    bgr = cv2.merge([colored[:, :, 0], colored[:, :, 1], colored[:, :, 2]])
    env[30 : 30 + h, 30 : 30 + w] = bgr[:, :, 0]  # gray page — keep single channel
    desk_photo = cv2.cvtColor(env, cv2.COLOR_GRAY2BGR)

    # slight perspective (skewed corners)
    H, W = desk_photo.shape[:2]
    src = np.float32([[8, 4], [W - 12, 18], [W, H], [0, H - 10]])
    dst = np.float32([[0, 0], [W - 1, 0], [W - 1, H - 1], [0, H - 1]])
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(desk_photo, M, (W, H))


def test_corner_detection_finds_page(synthetic_photo):
    corners = preprocessing.detect_document_corners(synthetic_photo)
    assert corners is not None
    assert corners.shape == (4, 2)


def test_warp_produces_a4_aspect(synthetic_photo):
    warped = preprocessing.document_warp(synthetic_photo, None)
    h, w = warped.shape[:2]
    assert 1.30 < h / w < 1.50  # A4 ≈ 1.414


def test_shadow_removal_brightens(synthetic_photo):
    gray = cv2.cvtColor(synthetic_photo, cv2.COLOR_BGR2GRAY)
    before = gray.mean()
    after = preprocessing.remove_shadows(gray).mean()
    assert after > before + 25


def test_deskew_corrects_small_rotation():
    # A wide dark ellipse mimics a tilted line block.
    page = np.full((600, 800), 250, dtype=np.uint8)
    cv2.ellipse(page, (400, 300), (280, 40), 0, 0, 360, 0, -1)
    straight, angle = preprocessing.deskew(page)
    assert angle == 0.0  # already straight → no rotation applied

    tilted = np.full((600, 800), 250, dtype=np.uint8)
    cv2.ellipse(tilted, (400, 300), (280, 40), -6, 0, 360, 0, -1)
    fixed, angle = preprocessing.deskew(tilted)
    assert 3 < abs(angle) < 10


def test_line_segmentation_finds_page_lines():
    page = np.full((1000, 700), 240, dtype=np.uint8)
    y = 80
    for i in range(5):
        cv2.rectangle(page, (60, y), (620 - i * 30, y + 26), 30, -1)
        y += 70 + i * 6
    boxes = layout.find_line_boxes(page)
    assert len(boxes) == 5
    ys = [b["bbox"][1] for b in boxes]
    assert ys == sorted(ys)  # top-to-bottom reading order


def test_paragraph_grouping_splits_on_big_gap():
    page = np.full((1400, 700), 240, dtype=np.uint8)
    # paragraph 1: three tight lines
    y = 100
    for _ in range(3):
        cv2.rectangle(page, (70, y), (600, y + 40), 30, -1)
        y += 110
    # paragraph 2 after a large vertical gap
    y += 400
    for _ in range(2):
        cv2.rectangle(page, (70, y), (600, y + 40), 30, -1)
        y += 110
    boxes = layout.find_line_boxes(page)
    paras = layout.group_paragraphs(boxes)
    assert len(paras) == 2


def test_assemble_text_joins_lines_and_paragraphs():
    lines = [
        {"i": 0, "text": "Q1: Define X"},
        {"i": 1, "text": "X is important because"},
        {"i": 2, "text": "of several reasons."},
        {"i": 3, "text": "Q2: Explain Y"},
    ]
    paragraphs = [
        {"lines": [0, 1, 2], "heading": False},
        {"lines": [3], "heading": True},
    ]
    text = layout.assemble_text(lines, paragraphs)
    assert text == "Q1: Define X\nX is important because\nof several reasons.\n\nQ2: Explain Y"


def test_recognizer_roundtrip():
    import numpy as np

    from backend.services import recognition as rec

    recognizer = rec.get_recognizer()
    assert recognizer.name == "mock"
    image = np.full((40, 300), 128, dtype=np.uint8)
    result = recognizer.recognize(image, index=2)
    assert "line 3" in result.text
    assert 0.0 < result.confidence < 1.0
