"""Handwriting recognition layer (Step 4).

Two providers behind one tiny interface:

- ``MockRecognizer``  — instant, offline, deterministic placeholder text.
  Lets the entire app (upload → editor → export) be demonstrated and tested
  before the TrOCR weights are downloaded, and keeps unit tests fast.
- ``TrOCRRecognizer`` — Microsoft TrOCR handwritten model through Hugging
  Face ``transformers``. Lazy-imported so the app still runs when torch is
  not installed. Produces an average token-probability confidence score.

Select the provider with ``SCANNER_RECOGNIZER=mock|trocr``.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Recognition:
    text: str
    confidence: float


class BaseRecognizer:
    name: str = "base"

    def recognize(self, image: np.ndarray, index: int = 0) -> Recognition:
        raise NotImplementedError


def _crop_to_grayscale(image: np.ndarray) -> np.ndarray:
    import cv2

    if image is None:
        return np.full((10, 10), 255, dtype=np.uint8)
    if image.ndim == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image


def ink_fraction(image: np.ndarray) -> float:
    """Share of dark pixels in the crop (0=paper only, 1=fully covered)."""
    gray = _crop_to_grayscale(image)
    return float(np.clip(1.0 - gray.mean() / 255.0, 0.0, 1.0))


class MockRecognizer(BaseRecognizer):
    """Deterministic stub recognition (never claimed to be real text)."""

    name = "mock"

    def recognize(self, image: np.ndarray, index: int = 0) -> Recognition:
        ink = ink_fraction(image)
        # Dense handwriting reads as "plausible", faint scribble less so —
        # enough to exercise the confidence colouring in the UI.
        confidence = float(np.clip(0.55 + ink * 2.5, 0.40, 0.95))
        confidence -= (index % 5) * 0.02
        text = f"(mock recognition) line {index + 1}"
        return Recognition(text=text, confidence=round(confidence, 3))


class TrOCRRecognizer(BaseRecognizer):
    """TrOCR handwritten-line recognition with token-probability confidence."""

    name = "trocr"

    def __init__(self) -> None:
        import threading

        self._device: str | None = None
        self._processor = None
        self._model = None
        self._lock = threading.Lock()
        self._loaded = False

    # ------------------------------------------------------------------ #
    def _ensure_model(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            from backend.config import settings

            import torch
            from transformers import TrOCRProcessor, VisionEncoderDecoderModel

            device = settings.device
            if device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            if settings.cpu_threads > 0:
                torch.set_num_threads(max(1, settings.cpu_threads))

            self._processor = TrOCRProcessor.from_pretrained(settings.trocr_model)
            self._model = VisionEncoderDecoderModel.from_pretrained(settings.trocr_model)
            self._model.to(device)
            self._model.eval()
            self._device = device
            self._loaded = True

    # ------------------------------------------------------------------ #
    def _prepare_image(self, image: np.ndarray):
        from PIL import Image

        gray = _crop_to_grayscale(image)
        h, w = gray.shape[:2]
        # TrOCR expects a reasonably sized line crop; pad to avoid clipping
        # touching strokes and upscale very short crops.
        pad = max(6, h // 20)
        padded = np.full((h + 2 * pad, w + 2 * pad), 255, dtype=np.uint8)
        padded[pad : pad + h, pad : pad + w] = gray
        if padded.shape[0] < 64:
            k = 64 / padded.shape[0]
            padded = np.array(
                Image.fromarray(padded).resize(
                    (max(16, int(padded.shape[1] * k)), 64), Image.LANCZOS
                )
            )
        pil = Image.fromarray(padded)
        if max(pil.size) > 1280:
            k = 1280 / max(pil.size)
            pil = pil.resize((max(16, int(pil.size[0] * k)), max(16, int(pil.size[1] * k))), Image.LANCZOS)
        return pil.convert("RGB")

    # ------------------------------------------------------------------ #
    def recognize(self, image: np.ndarray, index: int = 0) -> Recognition:
        import torch

        self._ensure_model()
        pil = self._prepare_image(image)
        pixel_values = self._processor(images=pil, return_tensors="pt").pixel_values
        pixel_values = pixel_values.to(self._device)

        with torch.inference_mode():
            generated = self._model.generate(
                pixel_values,
                num_beams=1,
                output_scores=True,
                return_dict_in_generate=True,
                max_new_tokens=64,
            )
        text = self._processor.batch_decode(generated.sequences, skip_special_tokens=True)[0]
        text = text.strip()

        # Confidence = mean probability of the tokens actually generated.
        probs: list[float] = []
        for step_logits in generated.scores:
            step_probs = torch.softmax(step_logits, dim=-1).max()
            probs.append(float(step_probs.item()))
        confidence = float(np.clip(np.mean(probs) if probs else 0.5, 0.0, 1.0))
        return Recognition(text=text, confidence=round(confidence, 3))


_instance: BaseRecognizer | None = None
_instance_lock = threading.Lock()


def get_recognizer() -> BaseRecognizer:
    """Return the configured provider, created once per process."""
    global _instance
    from backend.config import settings

    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = TrOCRRecognizer() if settings.recognizer == "trocr" else MockRecognizer()
    return _instance


def reset_recognizer() -> None:
    """Drop the cached provider (used by tests and provider switching)."""
    global _instance
    with _instance_lock:
        _instance = None
