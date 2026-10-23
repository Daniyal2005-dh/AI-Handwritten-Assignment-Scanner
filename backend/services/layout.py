"""Text-line segmentation and document layout reconstruction ("Step 3").

For v1 we assume single-column assignment pages, which covers handwritten
work well. Lines are found with a horizontal ink-projection profile on a
binarised page; paragraphs come from vertical gaps between lines, and a
simple height heuristic marks probable headings.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def binarise_ink(gray: np.ndarray) -> np.ndarray:
    """White-on-black ink mask: 255 where writing lies, 0 on paper."""
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    return cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 15
    )


def find_line_boxes(
    gray: np.ndarray,
    min_height: int = 8,
    min_width_fraction: float = 0.015,
    ink_fraction_threshold: float = 0.008,
) -> list[dict[str, Any]]:
    """Split the page into horizontal text bands (top-to-bottom reading order).

    A row counts as "active" when its ink density exceeds a fraction of the
    page width; runs of active rows become line candidates, tiny remnants
    (specks of noise) are dropped.
    """
    h, w = gray.shape[:2]
    binary = binarise_ink(gray)

    ink_per_row = binary.sum(axis=1) / 255.0
    active = ink_per_row >= max(3.0, w * ink_fraction_threshold)

    # Remove 1-row flicker (a 3-wide majority filter).
    active = np.convolve(active.astype(int), np.array([1, 1, 1]), mode="same") >= 2

    boxes: list[dict[str, Any]] = []
    min_w = max(12, int(w * min_width_fraction))
    run_start = None
    for y in range(h + 1):  # h sentinel closes the last run
        on = y < h and bool(active[y])
        if on and run_start is None:
            run_start = y
        elif not on and run_start is not None:
            y0, y1 = run_start, y
            run_start = None
            if y1 - y0 < min_height:
                continue
            cols = binary[y0:y1].sum(axis=0) / 255.0
            xs = np.where(cols > 0)[0]
            if xs.size == 0:
                continue
            x0, x1 = int(xs[0]), int(xs[-1])
            if x1 - x0 < min_w:
                continue
            boxes.append(
                {
                    "bbox": [x0, y0, x1 - x0, y1 - y0],
                }
            )
    return boxes


def group_paragraphs(
    boxes: list[dict[str, Any]],
    gap_factor: float = 1.7,
    heading_height_factor: float = 1.35,
) -> list[dict[str, Any]]:
    """Cluster consecutive lines into paragraphs using vertical gaps.

    Also flags a paragraph as a probable heading when its first line is
    markedly taller than the page's typical line height.
    """
    if not boxes:
        return []

    heights = [b["bbox"][3] for b in boxes]
    median_h = float(np.median(heights))

    # Downward gap between the bottom of one line and the top of the next.
    gaps = []
    for a, b in zip(boxes, boxes[1:]):
        gap = b["bbox"][1] - (a["bbox"][1] + a["bbox"][3])
        gaps.append(max(0, gap))
    median_gap = float(np.median(gaps)) if gaps else 0.0
    break_threshold = max(median_gap * gap_factor, 0.5 * median_h)

    paragraphs: list[dict[str, Any]] = []
    current: list[int] = [0]
    for i in range(1, len(boxes)):
        if gaps[i - 1] > break_threshold:
            paragraphs.append(current)
            current = [i]
        else:
            current.append(i)
    paragraphs.append(current)

    result: list[dict[str, Any]] = []
    for line_ids in paragraphs:
        first_h = boxes[line_ids[0]]["bbox"][3]
        heading = bool(
            first_h > heading_height_factor * median_h
            and len(line_ids) <= 2  # headings are short
        )
        result.append({"lines": line_ids, "heading": heading})
    return result


def assemble_text(lines: list[dict[str, Any]], paragraphs: list[dict[str, Any]]) -> str:
    """Rebuild a document string: line breaks inside paragraphs, blank line
    breaks between paragraphs (mirrors how people type assignments)."""
    if not lines:
        return ""
    parts: list[str] = []
    for para in paragraphs:
        text = "\n".join(lines[i]["text"] for i in para["lines"])
        parts.append(text)
    return "\n\n".join(parts)
