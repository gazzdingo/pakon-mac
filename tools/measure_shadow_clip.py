#!/usr/bin/env python3
"""Shadow-clip measurement — the Phase 6 acceptance-test instrument.

    python3 tools/measure_shadow_clip.py <tap-dir> [<tap-dir> ...]
    python3 tools/measure_shadow_clip.py --compare <old-tap-dir> <new-tap-dir>

WHY THIS EXISTS. docs/66-autotone-port-plan.md's Phase 6 hard acceptance
criterion for the analyzeAutoTone port is a shadow-clip percentage move
"clearly outside" a ~0.02-point noise band established by an earlier
controlled test (a correct FUGC-only fix moved 39.21% to 39.19% and that was
ruled a FAIL — noise, not a real improvement). That comparison was done by
hand at the time; this script is the checked-in, reusable replacement docs/66
asks for, so the next person (or the next re-run of THIS port) does not have
to re-derive the methodology. No prior checked-in script existed — grepped
docs/ and tools/ for "shadow" and "39.21"/"39.19" before writing this; both
numbers only ever appear as prose in docs/65 and docs/66, not as script
output.

WHAT "shadow-region-under-code-16" MEANS, PRECISELY. Two clipping statistics
appear in this project's history, both counting individual channel SAMPLES
(not pixels — an image is h*w*3 samples) whose value falls under a threshold,
expressed as a percentage of total samples:

  * shasta.go's own stand-in docstring: "8.65% of its own toned output
    samples land under code 257" — measured on the "shasta" tap, i.e. the
    toned RPD-12 (12-bit, 0..4095) output BEFORE the ICC hop.  257/4095 is
    the 12-bit code that lands on 8-bit code 16 (257/4095*255 ~= 16.0).
  * docs/66's acceptance criterion, "shadow-region-under-code-16 ... 39.21%"
    — measured on the FINAL rendered image, the 8-bit sRGB "icc" tap
    (0..255), samples with value < 16.

This script measures BOTH, on whichever taps are present in a tap-dir (a
directory main.go's -tap-dir flag writes: manifest.json + one file per stage,
per tools/ansel/pipeline/taps.go).  The icc-tap number (0..255, threshold 16)
is the one docs/66 names as the hard acceptance criterion and is what
--compare's verdict is based on; the shasta-tap number (0..4095, threshold
257) is reported alongside for corroboration only, matching docs/66's "same
standard already used for the inversion stage" instruction to pair a scripted
number with a direct look at the image.

CAPTURES. Tap directories are typically produced by rendering a frame under
captures/out_test/frames/ — this script itself never reads captures/, it only
reads whatever scratch tap-dir main.go was pointed at (main.go's own -tap-dir
output is NOT written under captures/ by convention in this project's usage,
and this script does not care where the tap-dir lives; it is the CALLER's
responsibility, per this project's standing rule, to point -tap-dir at a
scratch location and never commit it).  This script prints only aggregate
percentages, never pixel data, so its own output is safe to paste into a
report.

NOISE BAND. The known noise band from the FUGC control test is ~0.02
percentage points (39.21 -> 39.19). This script does not hardcode an
accept/reject threshold — that is a judgement call for whoever reads the
report, per docs/66's own wording ("clearly outside that noise band", not a
fixed number) — but it does print the delta as a multiple of 0.02 points to
make that judgement easy and consistent.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

NOISE_BAND_POINTS = 0.02  # percentage points; see module docstring.

# (tap name, dtype, max-code, shadow threshold-in-that-code-space, label)
TAP_SPECS = (
    ("icc", np.uint8, 255, 16, "final 8-bit sRGB (icc tap), code<16 of 255"),
    ("shasta", None, 4095, 257, "pre-ICC toned RPD-12 (shasta tap), code<257 of 4095"),
    ("ansel", None, 4095, 257, "pre-ICC toned RPD-12 (ansel tap), code<257 of 4095"),
)


def load_manifest(tap_dir: Path) -> dict:
    mf = tap_dir / "manifest.json"
    if not mf.exists():
        raise SystemExit(f"{tap_dir}: no manifest.json — not a tap-dir "
                          f"(render with main.go's -tap-dir flag first)")
    return json.loads(mf.read_text())


def load_tap(tap_dir: Path, manifest: dict, name: str):
    h, w = manifest["height"], manifest["width"]
    u8 = tap_dir / f"{name}.u8"
    f64 = tap_dir / f"{name}.f64"
    if u8.exists():
        return np.fromfile(u8, dtype=np.uint8).reshape(h, w, 3)
    if f64.exists():
        return np.fromfile(f64, dtype="<f8").reshape(h, w, 3)
    return None


def shadow_stats(tap_dir: Path) -> dict:
    """Every available shadow-clip statistic for one tap-dir."""
    manifest = load_manifest(tap_dir)
    out = {"tap_dir": str(tap_dir), "engine": manifest.get("engine", "?")}
    for name, _dtype, max_code, threshold, label in TAP_SPECS:
        arr = load_tap(tap_dir, manifest, name)
        if arr is None:
            continue
        arr = arr.astype(np.float64)
        n_samples = arr.size
        n_under = int(np.count_nonzero(arr < threshold))
        pct = 100.0 * n_under / n_samples
        out[name] = {
            "label": label,
            "threshold": threshold,
            "max_code": max_code,
            "n_samples": n_samples,
            "n_under": n_under,
            "pct_under": pct,
        }
    return out


def print_stats(stats: dict) -> None:
    print(f"{stats['tap_dir']}  (engine={stats['engine']})")
    for name, _dtype, _max_code, _threshold, _label in TAP_SPECS:
        if name not in stats:
            continue
        s = stats[name]
        print(f"  {name:<8} {s['label']}: "
              f"{s['pct_under']:.4f}% ({s['n_under']}/{s['n_samples']} samples)")


def compare(old_dir: Path, new_dir: Path) -> None:
    old = shadow_stats(old_dir)
    new = shadow_stats(new_dir)
    print("OLD (stand-in):")
    print_stats(old)
    print()
    print("NEW (real port):")
    print_stats(new)
    print()
    print("DELTA (new - old), the acceptance-relevant one is 'icc':")
    for name, _dtype, _max_code, _threshold, label in TAP_SPECS:
        if name not in old or name not in new:
            continue
        d = new[name]["pct_under"] - old[name]["pct_under"]
        mult = abs(d) / NOISE_BAND_POINTS
        flag = " <-- ACCEPTANCE METRIC" if name == "icc" else ""
        print(f"  {name:<8} {label}: {d:+.4f} points "
              f"({mult:.1f}x the {NOISE_BAND_POINTS}-point noise band){flag}")
    if "icc" in old and "icc" in new:
        d = new["icc"]["pct_under"] - old["icc"]["pct_under"]
        print()
        print(f"Hard acceptance criterion (docs/66 Phase 6): move must be "
              f"CLEARLY outside the ~{NOISE_BAND_POINTS}-point noise band "
              f"established by the earlier FUGC-only control test "
              f"(39.21% -> 39.19%, ruled a FAIL). Observed icc-tap move: "
              f"{d:+.4f} points ({abs(d) / NOISE_BAND_POINTS:.1f}x noise band).")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dirs", nargs="+", type=Path,
                    help="one or more tap-dirs (main.go -tap-dir output)")
    ap.add_argument("--compare", action="store_true",
                    help="treat exactly two dirs as (old, new) and print a delta/verdict")
    args = ap.parse_args()

    if args.compare:
        if len(args.dirs) != 2:
            raise SystemExit("--compare needs exactly two tap-dirs: old new")
        compare(args.dirs[0], args.dirs[1])
        return

    for d in args.dirs:
        print_stats(shadow_stats(d))
        print()


if __name__ == "__main__":
    main()
