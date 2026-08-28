#!/usr/bin/env python3
"""Subset JetBrains Mono into the four woff2 files the SVGs inline."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TTF_DIR = HERE.parent / "source" / "JetBrainsMono" / "fonts" / "ttf"
OUT = HERE / "fonts"

REGULAR = TTF_DIR / "JetBrainsMono-Regular.ttf"
SEMIBOLD = TTF_DIR / "JetBrainsMono-SemiBold.ttf"

RAMP = " .`:-=+*cs#%@"

# The stat graphics draw an 80-column terminal screen, so beyond basic latin
# they need the two blocks that make a screen look like one: box drawing
# (U+2500-257F) for the frames and block elements (U+2580-259F) for the bars,
# the sparkline and the year map. U+00B7 is the empty-cell dot.
SCREEN = "U+0020-007E,U+00B7,U+2500-257F,U+2580-259F"

# Headings are one rule line: uppercase, the two ends, and the horizontal run.
HEADINGS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789═╡╞"

JOBS = [
    (REGULAR, "jbmono-ramp.woff2", {"text": RAMP}),
    (SEMIBOLD, "jbmono-head.woff2", {"text": HEADINGS}),
    (REGULAR, "jbmono-400.woff2", {"unicodes": SCREEN}),
    (SEMIBOLD, "jbmono-600.woff2", {"unicodes": SCREEN}),
]


def subset(src: Path, dest: Path, extra: dict) -> None:
    cmd = [
        sys.executable, "-m", "fontTools.subset", str(src),
        f"--output-file={dest}",
        "--flavor=woff2",
        "--layout-features=",
        "--no-hinting",
        "--desubroutinize",
    ]
    if "text" in extra:
        cmd.append(f"--text={extra['text']}")
    if "unicodes" in extra:
        cmd.append(f"--unicodes={extra['unicodes']}")
    subprocess.check_call(cmd)


def main() -> None:
    if not REGULAR.exists() or not SEMIBOLD.exists():
        sys.exit(
            f"missing TTF at {TTF_DIR}\n"
            "unpack JetBrainsMono-2.304.zip into source/JetBrainsMono/"
        )
    OUT.mkdir(parents=True, exist_ok=True)
    for src, name, extra in JOBS:
        dest = OUT / name
        subset(src, dest, extra)
        print(f"{name:20} {dest.stat().st_size:6} bytes")


if __name__ == "__main__":
    main()
