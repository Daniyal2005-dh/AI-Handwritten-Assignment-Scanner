"""Generate PWA icons (any + maskable) into frontend/icons/."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "frontend" / "icons"


def make_icon(size: int, maskable: bool = False) -> Image.Image:
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(icon)

    # rounded gradient square
    scale = size / 512
    radius = int(90 * scale) if not maskable else 0
    top, bottom = (62, 125, 79), (125, 185, 92)  # garden green gradient
    grad = Image.new("RGB", (size, size))
    for y in range(size):
        t = y / size
        c = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        ImageDraw.Draw(grad).line([(0, y), (size, y)], fill=c)
    if radius:
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
        icon.paste(grad, (0, 0), mask)
    else:
        icon.paste(grad, (0, 0))

    # typeface: bold "AI" + underline; maskable keeps glyphs in the 80% safe zone
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", int(size * 0.42))
    except OSError:
        font = ImageFont.load_default()
    text = "AI"
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) // 2 - bbox[0]
    y = (size - th) // 2 - bbox[1]
    d.text((x, y), text, fill=(255, 255, 255, 255), font=font)

    # underline measured from where the glyphs actually landed
    drawn = d.textbbox((x, y), text, font=font)
    line_w = max(6, int(20 * scale))
    line_y = drawn[3] + int(28 * scale)
    line_x0, line_x1 = int(size * 0.32), int(size * 0.68)
    d.rounded_rectangle([line_x0, line_y, line_x1, line_y + line_w], radius=line_w // 2, fill=(255, 255, 255, 235))
    return icon


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        make_icon(size).save(OUT / f"icon-{size}.png")
        make_icon(size, maskable=True).save(OUT / f"icon-{size}-maskable.png")
    # apple touch icon (opaque, no alpha edges)
    make_icon(180).convert("RGB").save(OUT / "apple-touch-icon.png", "PNG")
    print(f"icons written to {OUT}")


if __name__ == "__main__":
    main()
