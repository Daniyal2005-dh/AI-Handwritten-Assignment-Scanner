"""Generate synthetic "handwritten" assignment pages with exact ground truth.

Usage:
    python scripts/make_sample_page.py --out data/samples --count 3

Each page gets:
  * a slightly rotated, shadowed photo of a rendered assignment
  * a matching `.gt.txt` file with the exact text rendered on it

Because the ground truth is known exactly, `scripts/evaluate.py` can report
CER/WER even before the IAM database is integrated.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFont

import numpy as np

BODY_CODE = """Name: Daniyal Hussain    Reg No: 2025-CS-101    Date: 14-10-2026

Q1. Explain the difference between a combinational circuit and a
sequential circuit. Give one example of each type and briefly
describe how a flip-flop behaves as a basic memory element.

A combinational circuit depends only on present inputs while a
sequential circuit depends on present inputs as well as past state.
Common examples are a binary adder and a synchronous counter.

Q2. Simplify the Boolean function F(A,B,C) = AB + AB' + A'C
using Boolean algebra laws and then verify the result with a
truth table showing all eight combinations of the inputs."""

BODY_FONT_SIZE = 38
LINE_STEP = 66
MARGIN = 150


def find_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = (
        ["segoeui.ttf", "arial.ttf"] if not bold else ["segoeuib.ttf", "arialbd.ttf"]
    )
    for root in (r"C:\Windows\Fonts", "/usr/share/fonts/truetype/dejavu"):
        for name in names:
            p = Path(root) / name
            if p.exists():
                try:
                    return ImageFont.truetype(str(p), size=size)
                except OSError:
                    continue
    return ImageFont.load_default()


def wrap(text: str, limit: int = 62) -> list[str]:
    """Split paragraphs into display lines (preserves lone heading lines)."""
    out = []
    for para in text.strip("\n").split("\n"):
        if not para.strip():
            out.append("")  # blank separator lines stay
            continue
        words = para.strip().split(" ")
        line = ""
        for word in words:
            trial = f"{line} {word}".strip()
            if len(trial) > limit and line:
                out.append(line)
                line = word
            else:
                line = trial
        if line:
            out.append(line)
    return out


def render_code_page(txt: str, rng: random.Random) -> Image.Image:
    lines = wrap(txt)
    width, height = 1200, 1700
    page = Image.new("L", (width, height), color=248)
    draw = ImageDraw.Draw(page)

    body_font = find_font(BODY_FONT_SIZE)
    heading_font = find_font(46, bold=True)

    y = 160
    for line in lines:
        if not line.strip():
            y += LINE_STEP
            continue
        font = heading_font if line is lines[0] else body_font
        if draw.textlength(line, font=font) > width - 2 * MARGIN and font is body_font:
            font = find_font(BODY_FONT_SIZE - 4)
        # word-by-word with jitter = a cheap "handwriting wobble"
        x = MARGIN + rng.randint(-8, 8)
        for word in line.split(" "):
            wpx = draw.textlength(word + " ", font=font)
            dy = rng.randint(-4, 4)
            draw.text((x, y + dy), word, fill=28, font=font)
            x += wpx + rng.randint(2, 10)
        y += LINE_STEP

    page = page.rotate(1.1, expand=False, fillcolor=248, resample=Image.BICUBIC)

    # Camera-like shading gradient + noise → shadows for the pipeline to fix
    arr = np.asarray(page).astype(np.float32)
    h, w = arr.shape
    gx = np.linspace(1.0, 0.70, w)[None, :]
    gy = np.linspace(1.0, 0.88, h)[:, None]
    arr *= np.minimum(gx, gy)
    arr += rng.gauss(0, 5.0, arr.shape)
    photo = np.clip(arr, 0, 255).astype(np.uint8)

    return Image.fromarray(photo).convert("L")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="data/samples")
    parser.add_argument("--count", type=int, default=3)
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    for i in range(1, args.count + 1):
        rng = random.Random(42 + i)
        title = f"Digital Logic Design — Assignment {i + 2}"
        sample = render_code_page(f"{title}\n\n{BODY_CODE.strip()}", rng)
        img_path = out / f"sample_{i}.png"
        gt_path = out / f"sample_{i}.gt.txt"
        sample.save(img_path)
        rendered_text = f"{title}\n\n{BODY_CODE.strip()}"
        # ground truth = the wrapped lines actually drawn, joined as paragraphs
        gt_path.write_text("\n".join(wrap(rendered_text)), encoding="utf-8")
        print(f"created {img_path} + {gt_path}")


if __name__ == "__main__":
    main()
