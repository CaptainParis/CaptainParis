#!/usr/bin/env python3
"""Turn a photo into ascii.svg — a self-typing, monochrome ASCII image.

Run it once; it is not on a schedule, unlike scripts/generate_stats.py.

    pip install pillow numpy opencv-python-headless
    python scripts/make_portrait.py source/avatar.jpg
    python scripts/embed_portrait_font.py

Add --cutout if the subject is a person against a busy background. That path
needs rembg and onnxruntime, and the first run downloads a ~176 MB model.

The grid bakes in an advance width of exactly 0.600 em (CHAR_W / FONT_SIZE), so
after generating, run scripts/embed_portrait_font.py to inline JetBrains Mono.
Otherwise a viewer whose default monospace is narrower — Consolas is ≈0.55 —
sees the image about 7% too narrow.

Motion is SMIL: each row is revealed by a clipPath wipe with a cursor block
riding its edge, staggered top to bottom, frozen at the end so it prints once
and stops.
"""
from __future__ import annotations

import argparse
import sys

import cv2
import numpy as np
from PIL import Image

RAMP = " .`:-=+*cs#%@"     # bright/sparse -> dark/dense; leading space = blank
COLS = 90                  # below ~88 the image muddies; far above it dominates
CLAHE_CLIP = 3.0           # higher amplifies texture into noise
GAMMA = 1.0                # ramp mapping exponent
CURVE = 1.45               # darkening curve; 1.7 is typical for a face
CROP_BOTTOM = 0.0          # fraction to trim off the bottom
ROW_RATIO = 0.48           # monospace cells are about twice as tall as wide

FG_LIGHT = "#6e7681"       # readable on GitHub light
FG_DARK = "#c9d1d9"        # and its dark-mode step
CHAR_W = 7.74              # 0.600 em at FONT_SIZE — keep these in step
FONT_SIZE = 12.9
LINE_H = 15
ROW_DELAY = 0.09           # per-row stagger, seconds
FAMILY = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"


def prep(path, crop=None, cutout=False, curve=CURVE, clahe_clip=CLAHE_CLIP):
    """Even the local contrast, then darken. Optional subject cut-out."""
    src = Image.open(path).convert("RGBA")
    if crop:
        src = src.crop(crop)

    alpha = np.array(src.split()[-1])
    if cutout:
        from rembg import remove
        src = remove(src)
        alpha = np.array(src.split()[-1])

    white = Image.new("RGBA", src.size, (255, 255, 255, 255))
    gray = np.array(Image.alpha_composite(white, src).convert("L"))

    gray = cv2.bilateralFilter(gray, 11, 50, 50)
    gray = cv2.createCLAHE(clipLimit=clahe_clip,
                           tileGridSize=(8, 8)).apply(gray)
    gray = (255.0 * (gray / 255.0) ** curve).astype("uint8")
    gray[alpha < 20] = 255
    return Image.fromarray(gray)


def to_lines(img, cols=COLS, gamma=GAMMA, crop_bottom=CROP_BOTTOM):
    w, h = img.size
    if crop_bottom:
        img = img.crop((0, 0, w, int(h * (1 - crop_bottom))))
        w, h = img.size

    rows = int(cols * (h / w) * ROW_RATIO)
    img = img.resize((cols, rows), Image.LANCZOS)
    px = np.array(img, dtype=np.uint8).reshape(-1)
    n = len(RAMP)

    out = []
    for r in range(rows):
        out.append("".join(
            RAMP[min(n - 1, int((1 - px[r * cols + c] / 255.0) ** gamma * n))]
            for c in range(cols)
        ).rstrip())

    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return out


def build_svg(lines, cols=COLS):
    pad = 14
    width = int(cols * CHAR_W + pad * 2)
    height = len(lines) * LINE_H + pad * 2

    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
         f'height="{height}" viewBox="0 0 {width} {height}" '
         f'font-family="{FAMILY}">',
         f'<style>.a{{fill:{FG_LIGHT}}}'
         f'@media(prefers-color-scheme:dark){{.a{{fill:{FG_DARK}}}}}</style>']

    for i, line in enumerate(lines):
        y = pad + i * LINE_H
        begin = f"{i * ROW_DELAY:.2f}s"
        end = f"{(i + 1) * ROW_DELAY:.2f}s"
        w = max(len(line), 1) * CHAR_W
        safe = (line.replace("&", "&amp;").replace("<", "&lt;")
                    .replace(">", "&gt;"))

        p.append(f'<clipPath id="c{i}"><rect x="{pad}" y="{y}" '
                 f'height="{LINE_H}" width="0">'
                 f'<animate attributeName="width" from="0" to="{w:.1f}" '
                 f'begin="{begin}" dur="{ROW_DELAY}s" fill="freeze"/>'
                 f'</rect></clipPath>')
        p.append(f'<g clip-path="url(#c{i})"><text xml:space="preserve" '
                 f'x="{pad}" y="{y + 11.2:.1f}" class="a" '
                 f'font-size="{FONT_SIZE}">{safe}</text></g>')
        p.append(f'<rect y="{y + 1}" width="6" height="12" class="a" '
                 f'opacity="0">'
                 f'<animate attributeName="x" from="{pad}" to="{pad + w:.1f}" '
                 f'begin="{begin}" dur="{ROW_DELAY}s" fill="freeze"/>'
                 f'<set attributeName="opacity" to="0.8" begin="{begin}"/>'
                 f'<set attributeName="opacity" to="0" begin="{end}"/></rect>')

    p.append("</svg>")
    return "".join(p)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("photo")
    ap.add_argument("out", nargs="?", default="ascii.svg")
    ap.add_argument("--crop", help="left,top,right,bottom, applied first")
    ap.add_argument("--cols", type=int, default=COLS)
    ap.add_argument("--curve", type=float, default=CURVE)
    ap.add_argument("--gamma", type=float, default=GAMMA)
    ap.add_argument("--cutout", action="store_true",
                    help="force the background to white with rembg")
    ap.add_argument("--preview", action="store_true",
                    help="print the ASCII to the terminal as well")
    args = ap.parse_args()

    crop = None
    if args.crop:
        parts = [int(v) for v in args.crop.split(",")]
        if len(parts) != 4:
            sys.exit("--crop needs four numbers: left,top,right,bottom")
        crop = tuple(parts)

    lines = to_lines(
        prep(args.photo, crop, cutout=args.cutout, curve=args.curve),
        cols=args.cols,
        gamma=args.gamma,
    )
    if args.preview:
        print("\n".join(lines))

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(build_svg(lines, cols=args.cols))
    print(f"wrote {args.out} — {len(lines)} rows, {args.cols} columns")
    print("next: python scripts/embed_portrait_font.py")


if __name__ == "__main__":
    main()
