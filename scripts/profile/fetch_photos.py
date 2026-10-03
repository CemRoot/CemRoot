#!/usr/bin/env python3
"""Download the portrait tiles used by the research card (once).

Photos come from Unsplash (free to use under the Unsplash License) and are
committed to photos/ so builds stay deterministic; existing files are kept.
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "photos"

# Unsplash photo ids, in tile order (left to right, top to bottom)
PHOTOS = [
    "1494790108377-be9c29b29330",
    "1507003211169-0a1dd7228f2d",
    "1438761681033-6461ffad8d80",
    "1500648767791-00dcc994a43e",
    "1534528741775-53994a69daeb",
    "1472099645785-5658abf4ff4e",
]


def main():
    OUT.mkdir(exist_ok=True)
    failed = 0
    for i, pid in enumerate(PHOTOS):
        path = OUT / f"face-{i}.jpg"
        if path.exists():
            continue
        url = f"https://images.unsplash.com/photo-{pid}?w=240&h=240&fit=crop&crop=faces&q=72&fm=jpg"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "profile-assets"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
        except OSError as exc:
            print(f"skip {pid}: {exc}", file=sys.stderr)
            failed += 1
            continue
        if not data.startswith(b"\xff\xd8") or len(data) < 4000:
            print(f"skip {pid}: not a JPEG", file=sys.stderr)
            failed += 1
            continue
        path.write_bytes(data)
        print(f"{path.name}  {len(data) // 1024} KB")
    if failed:
        print(f"{failed} photo(s) missing; the card falls back to drawn silhouettes", file=sys.stderr)


if __name__ == "__main__":
    main()
