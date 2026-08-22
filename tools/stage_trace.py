#!/usr/bin/env python3
"""Per-channel measurements at EVERY pipeline stage, against the vendor.

Why this exists
---------------
docs/74 §126-§132 chased the washed-out defect one stage at a time, and four
hypotheses in a row were refuted by their own evidence -- each because of an
unstated assumption about WHAT was being measured (a grey ramp for a 3-channel
transform, a toned file mistaken for the invert output, a data maximum read as
a format ceiling, a linear buffer compared against log-domain data). Measuring
one stage at a time is what made those mistakes easy to miss.

This measures every stage in one pass, in one place, with the units named, so
the numbers can be read across rather than compared from memory between
sessions.

What it reports, per channel, per stage:
    p1 / p50 / p99      the distribution
    span = p99 - p1     the width, which is what sets the ICC's local slope
    spread max/min      per-channel inequality (1.0 = channels equalised)
    decades             log10(p99/p1) where the domain is linear -- this is
                        scale-invariant and so is directly comparable to the
                        vendor's own captured buffers

Vendor references, and their limits (all established in docs/74):
    poly_input_r      raw 14-bit LINEAR R plane, vendor-side (§131.4). FIRST
                      call only -- later calls are in-place-contaminated per
                      the hook table's own row.
    AA*.tif           vendor RENDERED sRGB, 8-bit.
    rawAA*.tif        vendor raw export, 8-bit uint8 (§130.2) -- NOT linear
                      14-bit, so it cannot be fed through the invert. Usable
                      only for slope-per-decade, which is scale-invariant.

Usage:
    python3 tools/stage_trace.py <render_dir> [frame] [capture.jsonl]
"""
import json
import sys
from pathlib import Path

import numpy as np

try:
    import imageio.v3 as iio
except ImportError:
    sys.exit("needs imageio")


def stats(a):
    p1, p50, p99 = np.percentile(a, [1, 50, 99])
    return p1, p50, p99, p99 - p1


def report(name, img, linear=False):
    """img: HxWx3. `linear` marks a domain where decades are meaningful."""
    print(f"\n{name}")
    spans = []
    for c, nm in enumerate("RGB"):
        p1, p50, p99, span = stats(img[..., c])
        spans.append(span)
        dec = ""
        if linear and p1 > 0:
            dec = f"   decades {np.log10(p99 / p1):6.3f}"
        print(f"    {nm}  p1 {p1:8.1f}  p50 {p50:8.1f}  p99 {p99:8.1f}"
              f"  span {span:8.1f}{dec}")
    print(f"    per-channel span spread max/min = {max(spans)/min(spans):.4f}"
          f"   (1.0 = equalised)")
    return spans


def main(argv):
    d = Path(argv[1] if len(argv) > 1 else ".")
    frame = argv[2] if len(argv) > 2 else "05"
    F = d / "frames"
    print(f"stage trace: {d.name}  frame {frame}")
    print("=" * 70)

    stages = [
        ("1. CAPTURE   raw14 (linear sensor)", f"{frame}_raw14.tiff", 1.0, True),
        ("2. INVERT    rpd16 (log domain)", f"{frame}_rpd16.tiff", 1 / 16.0, False),
        ("3. TONE      ansel_rpd16 (post autoTone)", f"{frame}_ansel_rpd16.tiff",
         1 / 16.0, False),
    ]
    ours = {}
    for label, fn, scale, linear in stages:
        p = F / fn
        if not p.is_file():
            print(f"\n{label}\n    MISSING: {p.name}")
            continue
        img = iio.imread(p).astype(np.float64) * scale
        ours[label] = report(label, img, linear=linear)

    p = F / f"{frame}_srgb.png"
    if p.is_file():
        from PIL import Image
        img = np.asarray(Image.open(p).convert("RGB"), dtype=np.float64)
        report("4. ICC       srgb (final, 0..255)", img)

    # --- vendor side -----------------------------------------------------
    cap = argv[3] if len(argv) > 3 else None
    if cap and Path(cap).is_file():
        print("\n" + "=" * 70)
        print("VENDOR (poly_input_r, raw 14-bit LINEAR, FIRST call only --")
        print("later calls are in-place-contaminated, docs/74 §131.4)")
        for line in open(cap):
            rec = json.loads(line)
            if (rec.get("kind") == "buffer_dump"
                    and rec.get("label") == "poly_input_r"
                    and rec.get("readable")):
                v = np.frombuffer(bytes.fromhex(rec["hex"]), "<u2").astype(np.float64)
                p1, p50, p99, span = stats(v)
                print(f"\n    call {rec['call_id']}  R plane  n={v.size}")
                print(f"    p1 {p1:8.1f}  p50 {p50:8.1f}  p99 {p99:8.1f}"
                      f"  span {span:8.1f}   decades {np.log10(p99/p1):6.3f}")
                print("\n    Compare ONLY against stage 1 (both linear).")
                print("    Comparing it to stages 2-4 is a domain error.")
                break

    print("\n" + "=" * 70)
    print("Reading it: span sets the ICC's local slope (wider span -> shallower")
    print("slope, since the output range is fixed). Per-channel spread carries")
    print("through unchanged from stage 1 unless something equalises it.")


if __name__ == "__main__":
    main(sys.argv)
