#!/usr/bin/env python3
"""Extract the raw 14-bit sensor plane captured by the ``poly_input_r`` hook
row into a flat binary (``pakonscan.bin`` by default).

WHY THIS EXISTS
===============
docs/74 §157 built a same-frame comparison against the vendor by feeding
`rawAA001.tif` -- the PSI "raw" TIFF export -- through this port. That export is
**8-bit** (195 distinct levels), so quantisation is an error floor the test
cannot see past, and only one such pair exists.

The `tlb_polypixel` hook row already captures something strictly better: the
**raw 14-bit planar frame PolyPixel reads**, before the polynomial and before
the log. PolyPixel is in-place, so at ENTRY the dump is pre-poly sensor-domain
data. The row was widened to 0x84000 bytes (docs/74 §60) specifically so the
whole frame lands in ONE dump -- 245*367*3 planes * 2 bytes = 539490 = 0x83B62,
with R at base, G at base + w*h*2, B at base + w*h*4 (PolyPixel's own
`lea ebx,[edx+eax*2]` / `lea ebp,[edx+eax*4]` at 0x1000d8ce-0x1000d8e3).

So a real 14-bit raw frame is already in hand from past captures, at analysis
resolution (245x367) rather than the 2941x1960 of the TIFF export.

WHAT THIS IS AND IS NOT
=======================
* It is tier-2 evidence (live hardware hook capture), not tier 1.
* The geometry (w=0xf5, h=0x16f) is read from the capture's own stack dwords
  where present, and only falls back to 245x367 if absent -- a mismatch is
  reported, never silently assumed.
* This is the *analysis* image PolyPixel runs on, NOT the full-resolution scan.
  Do not describe it as "the scan"; it is the frame the tone chain analyses.

Usage:
    python3 tools/re/extract_poly_raw.py <capture.jsonl> [out.bin]
    python3 tools/re/extract_poly_raw.py --scan          # list candidates
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TMP = Path("/Users/guy/.claude-account-1/jobs/5e3f6f65/tmp")
DEFAULT_OUT = TMP / "pakonscan.bin"

#: confirmed live, v10 (docs/74 §59) -- NOT a guess, but still cross-checked
#: against the capture's own stack dwords when those are present.
FALLBACK_W, FALLBACK_H = 245, 367


def iter_rows(path: Path):
    with path.open("r", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or "poly_input_r" not in line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def find_hex(obj):
    """Return (hexstring, container) for the poly_input_r payload."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and "poly_input_r" in str(k) and len(v) > 64:
                return v, obj
            if isinstance(v, str) and len(v) > 4096 and k in (
                    "poly_input_r", "data", "bytes", "hex"):
                return v, obj
            r = find_hex(v)
            if r[0]:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_hex(v)
            if r[0]:
                return r
    return None, None


def scan(paths) -> int:
    print(f"{'capture':44} {'rows':>5} {'largest dump':>13}")
    print("-" * 66)
    best = []
    for p in sorted(paths):
        n, mx = 0, 0
        for row in iter_rows(p):
            h, _ = find_hex(row)
            if h:
                n += 1
                mx = max(mx, len(h) // 2)
        if n:
            print(f"{p.name:44} {n:5d} {mx:10d} B")
            best.append((mx, n, p))
    if best:
        best.sort(reverse=True)
        mx, n, p = best[0]
        print(f"\nlargest: {p.name}  ({mx} bytes)")
        full = FALLBACK_W * FALLBACK_H * 3 * 2
        print(f"a full 3-plane frame at {FALLBACK_W}x{FALLBACK_H} is "
              f"{full} bytes (0x{full:X})")
        print("FULL FRAME PRESENT" if mx >= full else
              f"PARTIAL -- {mx/full*100:.1f}% of a frame; "
              f"cannot reconstruct the whole image from this")
    return 0


def main(argv) -> int:
    if not argv or argv[0] == "--scan":
        return scan(TMP.glob("*.jsonl"))
    src = Path(argv[0])
    out = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUT
    if not src.is_file():
        print(f"no such capture: {src}")
        return 2

    best_hex, best_row = None, None
    for row in iter_rows(src):
        h, container = find_hex(row)
        if h and (best_hex is None or len(h) > len(best_hex)):
            best_hex, best_row = h, container
    if not best_hex:
        print(f"no poly_input_r payload found in {src.name}")
        return 1

    raw = bytes.fromhex(best_hex.strip())
    out.write_bytes(raw)
    full = FALLBACK_W * FALLBACK_H * 3 * 2
    print(f"wrote {out}  ({len(raw)} bytes, 0x{len(raw):X})")
    print(f"expected full 3-plane frame at {FALLBACK_W}x{FALLBACK_H}: "
          f"{full} bytes")
    if len(raw) < full:
        print(f"PARTIAL: {len(raw)/full*100:.1f}% of a frame -- "
              f"the tail planes are truncated")
    else:
        print("FULL FRAME: R at 0, G at w*h*2, B at w*h*4 (planar int16)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
