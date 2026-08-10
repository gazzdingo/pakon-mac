#!/usr/bin/env python3
"""Compare a Wine/Frida PIAnselAddScene dump to host ``poly_hwc``.

Settles docs/58 §3.5 residual: AddScene planar samples should match
F-135 stage-2 poly output (not dens-LUT / not raw 14-bit), bit-exact on
the dumped triplets when the same pre-poly pixels are known.

Two modes
---------

1. **dump-only check** (no raw strip): classify dumped samples as
   ``rpd12`` (≤4095, matches poly range) vs ``raw14`` (≤16383).
   If dumps look like raw14, dens/poly never ran before AddScene
   *or* the Frida heuristic grabbed the wrong pointer.

2. **paired compare**: ``--raw-rgb R,G,B`` (or a JSON list of triplets
   that were the *pre-poly* inputs for those sample indices) vs dump
   ``samples``. Host runs ``poly_pixel`` / ``poly_hwc`` and counts
   mismatches.

Dump format: JSONL from ``tools/addscene_wine_dump.js``::

    {"i":0,"desc":{"dmin_r":…,"dmin_g":…,"dmin_b":…},
     "planar":{"hint":"maybe_12bit_rpd","n":2000,"samples":[[r,g,b],…]}}

Usage::

    python3 tools/pakon_addscene_compare.py classify /tmp/addscene_dump.jsonl
    python3 tools/pakon_addscene_compare.py vs-poly /tmp/addscene_dump.jsonl \\
        --raw-json captures/decoded/addscene_raw_triplets.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pakon_color as pc  # noqa: E402


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def classify_samples(samples: list[list[int]]) -> dict:
    flat = [v for t in samples for v in t]
    if not flat:
        return {"empty": True}
    mx, mn = max(flat), min(flat)
    return {
        "n": len(samples),
        "min": mn,
        "max": mx,
        "mean": [sum(t[c] for t in samples) / len(samples) for c in range(3)],
        "domain": (
            "empty" if mx == 0 else
            "rpd12_or_poly" if mx <= 4095 else
            "raw14_or_lut16" if mx <= 16383 else
            "over_14bit"
        ),
    }


def cmd_classify(path: Path) -> int:
    rows = load_jsonl(path)
    if not rows:
        print(f"{path}: no records")
        return 1
    print(f"{path}: {len(rows)} AddScene call(s)")
    for rec in rows:
        desc = rec.get("desc") or {}
        print(f"  #{rec.get('i')} dmin RGB="
              f"({desc.get('dmin_r')}, {desc.get('dmin_g')}, {desc.get('dmin_b')}) "
              f"case={desc.get('case')}")
        planar = rec.get("planar")
        if not planar or not planar.get("samples"):
            print("       planar: (none — Frida heuristic missed the buffer)")
            continue
        stats = classify_samples(planar["samples"])
        print(f"       planar hint={planar.get('hint')} n={planar.get('n')} "
              f"domain={stats['domain']} min={stats['min']} max={stats['max']} "
              f"mean={[round(x, 1) for x in stats['mean']]}")
        print(f"       first3={planar['samples'][:3]}")
    print()
    print("Reading:")
    print("  domain=rpd12_or_poly  → consistent with TLB poly / no dens LUT")
    print("  domain=raw14_or_lut16 → still 14-bit *or* wrong pointer; pair with vs-poly")
    return 0


def cmd_vs_poly(path: Path, raw_json: Path | None,
                raw_rgb: list[tuple[int, int, int]] | None) -> int:
    rows = load_jsonl(path)
    if raw_json:
        raw_rgb = [tuple(t) for t in json.loads(raw_json.read_text())]
    if not raw_rgb:
        print("need --raw-json or --raw-rgb for bit-exact compare", file=sys.stderr)
        return 2

    coeffs = pc.load_unit_matrix()
    expect = [pc.poly_pixel(t, coeffs) for t in raw_rgb]
    print(f"poly coeffs diag {coeffs[0]:.6f} {coeffs[11]:.6f} {coeffs[22]:.6f}")
    print(f"raw triplets: {len(raw_rgb)}")

    any_planar = False
    worst = 0
    matched_calls = 0
    for rec in rows:
        planar = rec.get("planar") or {}
        samples = planar.get("samples") or []
        if not samples:
            continue
        any_planar = True
        n = min(len(samples), len(expect))
        bad = 0
        for i in range(n):
            got = tuple(int(x) for x in samples[i])
            ref = expect[i]
            if got != ref:
                bad += 1
                if bad <= 5:
                    print(f"  #{rec.get('i')}[{i}] raw={raw_rgb[i]} "
                          f"poly={ref} dump={got}")
        print(f"  #{rec.get('i')}: {n - bad}/{n} match "
              f"({'OK' if bad == 0 else 'DIFF'})")
        if bad == 0 and n > 0:
            matched_calls += 1
        worst = max(worst, bad)

    if not any_planar:
        print("no planar samples in dump — refine Frida heuristic or pass "
              "explicit plane base via ADDSCENE env once known")
        return 1
    if worst == 0:
        print("PASS — AddScene dump matches host poly_hwc / poly_pixel")
        print("docs/58 §3.5 residual: dens LUT not applied before AddScene")
        return 0
    print(f"FAIL — {worst} mismatched triplets on at least one call "
          f"({matched_calls} clean calls)")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("classify", help="summarise dump domains")
    c.add_argument("dump")

    v = sub.add_parser("vs-poly", help="bit-exact vs poly_pixel")
    v.add_argument("dump")
    v.add_argument("--raw-json", type=Path,
                   help="JSON list of pre-poly [R,G,B] triplets")
    v.add_argument("--raw-rgb", action="append", default=[],
                   help="one R,G,B triplet (repeatable)")

    args = ap.parse_args()
    if args.cmd == "classify":
        return cmd_classify(Path(args.dump))

    raw = []
    for s in args.raw_rgb:
        parts = [int(x) for x in s.replace(" ", "").split(",")]
        if len(parts) != 3:
            raise SystemExit(f"bad --raw-rgb {s!r}")
        raw.append(tuple(parts))
    return cmd_vs_poly(Path(args.dump), args.raw_json, raw or None)


if __name__ == "__main__":
    sys.exit(main())
