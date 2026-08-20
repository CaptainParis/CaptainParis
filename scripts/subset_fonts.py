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
HEADINGS = "abcdefghijklmnopqrstuvwxyz "

JOBS = [
    (REGULAR, "jbmono-ramp.woff2", {"text": RAMP}),
    (SEMIBOLD, "jbmono-head.woff2", {"text": HEADINGS}),
    (REGULAR, "jbmono-400.woff2", {"unicodes": "U+0020-007E"}),
    (SEMIBOLD, "jbmono-600.woff2", {"unicodes": "U+0020-007E"}),
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
