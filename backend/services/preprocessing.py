"""OpenCV document enhancement pipeline.

Implements "Step 2 — Preprocess image" of the project plan:
detect page boundaries -> correct perspective -> remove shadows ->
straighten (deskew) -> improve contrast.

Every step is a separate function so the evaluation script later can run
ablation studies (e.g. "does shadow removal actually improve CER?").
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# A4 aspect ratio (width / height) — pages are warped onto this geometry.
TARGET_ASPECT = 210.0 / 297.0


@dataclass
class PreprocessResult:
    processed: np.ndarray       # enhanced grayscale page, A4 aspect
    corners: np.ndarray         # 4x2 page corners found on the source photo
    rotation_angle: float       # degrees of deskew applied


def order_corners(pts: np.ndarray) -> np.ndarray:
    """Return 4 points ordered as top-left, top-right, bottom-right, bottom-left.

    tl minimises x+y, br maximises it; tr maximises x-y (large x, small y),
    bl minimises x-y (small x, large y).
    """
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    s = pts.sum(axis=1)
    d = pts[:, 0] - pts[:, 1]
    tl, br = pts[np.argmin(s)], pts[np.argmax(s)]
    tr, bl = pts[np.argmax(d)], pts[np.argmin(d)]
    return np.array([tl, tr, br, bl], dtype=np.float32)


def detect_document_corners(image: np.ndarray) -> np.ndarray | None:
    """Find the four page corners in a photo, or None if no page-like contour exists.

    Strategy: Canny edges -> largest quadrilateral contour. Falls back to the
    full image frame (already-scanned pages need no correction).
    """
    h, w = image.shape[:2]
    # Work on a downscaled copy; corner precision does not suffer meaningfully.
    scale = 1000.0 / max(h, w)
    resized = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY) if resized.ndim == 3 else resized
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    edges = cv2.Canny(blurred, 40, 120)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    frame_area = resized.shape[0] * resized.shape[1]
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:6]:
        area = cv2.contourArea(contour)
        if area < 0.15 * frame_area:
            break  # contours are sorted; everything after this is too small
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        if len(approx) == 4:
            corners = approx.reshape(4, 2) / scale
            return order_corners(corners)
    return None


def document_warp(
    image: np.ndarray,
    corners: np.ndarray | None,
    aspect: float = TARGET_ASPECT,
    max_width: int = 1700,
) -> np.ndarray:
    """Perspective-correct the page onto an upright A4-shaped canvas."""
    h, w = image.shape[:2]
    if corners is None:
        corners = order_corners([(0, 0), (w - 1, 0), (w - 1, h - 1), (0, h - 1)])
    tl, tr, br, bl = corners

    top_w = np.linalg.norm(tr - tl)
    bottom_w = np.linalg.norm(br - bl)
    width = max(top_w, bottom_w)
    height = width / aspect

    src = np.float32([tl, tr, br, bl])
    dst = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    matrix = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(
        image, matrix, (int(width), int(height)),
        flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE,
    )
    if warped.shape[1] > max_width:
        k = max_width / warped.shape[1]
        warped = cv2.resize(warped, (max_width, int(warped.shape[0] * k)))
    return warped


def remove_shadows(gray: np.ndarray, kernel_size: int = 31) -> np.ndarray:
    """Normalise illumination by dividing by an estimated background.

    The background is estimated with a large morphological close + median blur
    (paper texture and text are smaller than the kernel), so dividing the page
    by it flattens shadows and uneven lighting while keeping the ink dark.
    """
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    background = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
    background = cv2.medianBlur(background, kernel_size)
    return cv2.divide(gray, background, scale=255)


def denoise(gray: np.ndarray) -> np.ndarray:
    """Edge-preserving smoothing (safe for thin handwriting)."""
    return cv2.bilateralFilter(gray, 5, 40, 40)


def deskew(gray: np.ndarray, max_angle: float = 15.0, min_angle: float = 0.4):
    """Straighten text that is slightly rotated. Returns (image, angle_degrees)."""
    binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(binary > 0))
    if len(coords) < 50:
        return gray, 0.0
    angle = cv2.minAreaRect(coords.astype(np.float32))[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) < min_angle or abs(angle) > max_angle:
        return gray, 0.0
    h, w = gray.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        gray, matrix, (w, h),
        flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=255,
    )
    return rotated, float(angle)


def improve_contrast(gray: np.ndarray) -> np.ndarray:
    """Adaptive histogram equalisation to lift faint pencil strokes."""
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def preprocess_page(
    image: np.ndarray,
    max_width: int = 1700,
    use_corner_detection: bool = True,
    use_shadow_removal: bool = True,
    use_denoise: bool = True,
    use_deskew: bool = True,
    use_contrast: bool = True,
) -> PreprocessResult:
    """Run the full enhancement pipeline. Flags exist so the evaluation script
    can switch steps off for ablation experiments."""
    warped = document_warp(
        image,
        detect_document_corners(image) if use_corner_detection else None,
        max_width=max_width,
    )
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY) if warped.ndim == 3 else warped

    if use_shadow_removal:
        gray = remove_shadows(gray)
    if use_denoise:
        gray = denoise(gray)
    if use_deskew:
        gray, angle = deskew(gray)
    else:
        angle = 0.0
    if use_contrast:
        gray = improve_contrast(gray)

    return PreprocessResult(processed=gray, corners=None, rotation_angle=angle)
