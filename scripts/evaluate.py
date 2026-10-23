"""Week 4 evaluation: CER/WER on generated (or real) pages with ground truth.

Usage:
    python scripts/evaluate.py                       # data/samples mock check
    SCANNER_RECOGNIZER=trocr python scripts/evaluate.py   # real TrOCR model

For every ``*.png`` in the directory whose sidecar ``*.gt.txt`` exists, the
script runs the same pipeline the API runs (preprocess → segment → recognise),
then reports Character Error Rate and Word Error Rate.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2


def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = curr
    return prev[-1]


def cer(reference: str, hypothesis: str) -> float:
    ref = reference.replace("\n", "").strip()
    hyp = hypothesis.replace("\n", "").strip()
    if not ref:
        return 0.0 if not hyp else 1.0
    return levenshtein(ref, hyp) / len(ref)


def wer(reference: str, hypothesis: str) -> float:
    """Word Error Rate: minimum word-level edit distance / reference words."""
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    import numpy as np

    n, m = len(ref_words), len(hyp_words)
    dp = np.zeros((n + 1, m + 1), dtype=np.int32)
    dp[:, 0] = np.arange(n + 1)
    dp[0, :] = np.arange(m + 1)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            dp[i, j] = min(
                dp[i - 1, j] + 1,
                dp[i, j - 1] + 1,
                dp[i - 1, j - 1] + (ref_words[i - 1] != hyp_words[j - 1]),
            )
    return int(dp[n][m]) / n


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples-dir", default="data/samples")
    parser.add_argument("--csv", default=None, help="optional CSV output file")
    args = parser.parse_args()

    from backend.config import settings
    from backend.services import layout, preprocessing, recognition

    samples = Path(args.samples_dir)
    pairs = [
        (gt.with_name(gt.stem.replace(".gt", "") + ".png"), gt)
        for gt in sorted(samples.glob("*.gt.txt"))
    ]
    if not pairs:
        print("No samples found. Run: python scripts/make_sample_page.py")
        sys.exit(1)

    recognizer = recognition.get_recognizer()
    recognizer_name = type(recognizer).__name__
    if recognizer_name == "MockRecognizer":
        print("WARNING: mock recognizer — scores are meaningless placeholders.")
        print("Run with SCANNER_RECOGNIZER=trocr for real model evaluation.\n")

    rows = []
    for img_path, gt_path in pairs:
        reference = gt_path.read_text(encoding="utf-8")
        bgr = cv2.imread(str(img_path))
        if bgr is None:
            print(f"skip {img_path.name}: unreadable")
            continue
        result = preprocessing.preprocess_page(bgr, max_width=settings.processed_width)
        boxes = layout.find_line_boxes(result.processed)
        paragraphs = layout.group_paragraphs(boxes)
        hyp_lines = []
        for i, box in enumerate(boxes):
            x, y, w, h = box["bbox"]
            crop = result.processed[y : y + h, x : x + w]
            hyp_lines.append(recognizer.recognize(crop, index=i).text)
        hypothesis = layout.assemble_text(
            [{"i": i, "text": t} for i, t in enumerate(hyp_lines)], paragraphs
        )
        c = cer(reference, hypothesis)
        w_ = wer(reference, hypothesis)
        rows.append((img_path.name, type(recognizer).__name__, c, w_))
        print(f"{img_path.name:16s}  CER {c:6.1%}   WER {w_:6.1%}")

    if rows:
        avg_c = sum(r[2] for r in rows) / len(rows)
        avg_w = sum(r[3] for r in rows) / len(rows)
        print("-" * 44)
        print(f"{'MEAN':16s}  CER {avg_c:6.1%}   WER {avg_w:6.1%}")
        if args.csv:
            with open(args.csv, "w", encoding="utf-8", newline="") as fh:
                fh.write("file,recognizer,cer,wer\n")
                for name, rec_name, c, w_ in rows:
                    fh.write(f"{name},{rec_name},{c:.4f},{w_:.4f}\n")
            print(f"CSV written to {args.csv}")


if __name__ == "__main__":
    main()
