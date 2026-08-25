#!/usr/bin/env python3
"""Read the vendor's own ``area_image_apply_lut`` transfer LUTs out of a live
capture, and compare them against this port's reconstructed F-135 invert.

WHY
===
`pakon_decode.py` is explicit that the F-135 invert is NOT a port:

    F135_INVERT_PORTED = False
    "No DLL call site computes what f135_rom12_to_rpd12 computes.
     Every constant used below is the vendor's; the arrangement is ours.
     Rendered F-135 colour is provisional."

docs/74 §158 + the full-chain harness narrowed the remaining colour gap to
upstream of `real_auto_tone` (the tone chain and ICC are bit-exact against the
DLL on a real full frame; DRA cannot produce the offset). The invert is the last
unverified stage in that upstream, and it is the one that sets the tonal anchor.

The `area_image_apply_lut` hook row dumps `r_lut`/`g_lut`/`b_lut` at 8192 bytes
each -- 4096 entries of int16, i.e. a complete 12-bit transfer table. If the
vendor's inversion is table-driven, this IS the vendor's inversion curve,
captured on real hardware.

WHAT THIS ESTABLISHES, AND WHAT IT DOES NOT
===========================================
* Tier 2 (live hardware hook capture). Reading a table the DLL was about to
  apply is strong evidence about WHAT is applied; it is not tier 1 and does not
  by itself prove which stage builds the table or when.
* `LogExtraDumps` fires on ENTRY only, so these are the tables as handed TO
  apply_lut -- inputs, not outputs. That is what we want here.
* Whether this table is "the invert" is a HYPOTHESIS this script tests
  (monotonicity, direction, shape), not an assumption. A rising table would
  mean it is not an inversion at all.

Usage:  python3 tools/re/extract_area_luts.py [capture.jsonl]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

TMP = Path("/Users/guy/.claude-account-1/jobs/5e3f6f65/tmp")
DEFAULT = TMP / "live_hooks_20260819-121153.jsonl"
NAMES = ("r_lut", "g_lut", "b_lut")


def walk(obj, want, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in want and isinstance(v, str) and len(v) > 256:
                out[k] = v
            else:
                walk(v, want, out)
    elif isinstance(obj, list):
        for v in obj:
            walk(v, want, out)


def luts_from(path: Path):
    """Yield (r, g, b) int16 arrays per apply_lut CALL.

    The capture emits one JSON record per dump -- ``{"kind":"buffer_dump",
    "hook_id":..., "call_id":..., "label":"r_lut", "hex":...}`` -- so the three
    planes are three separate lines sharing a ``call_id``, not one record with
    three fields. Group by call_id.
    """
    pending: dict[str, dict[str, str]] = {}
    with path.open("r", errors="replace") as fh:
        for line in fh:
            if "_lut" not in line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            lbl = row.get("label")
            if lbl not in NAMES or not isinstance(row.get("hex"), str):
                continue
            key = f"{row.get('hook_id')}#{row.get('call_id')}"
            pending.setdefault(key, {})[lbl] = row["hex"]
            got = pending[key]
            if len(got) == 3:
                try:
                    arrs = [np.frombuffer(bytes.fromhex(got[n].strip()),
                                          dtype="<i2") for n in NAMES]
                except ValueError:
                    pending.pop(key, None)
                    continue
                pending.pop(key, None)
                if all(a.size >= 4096 for a in arrs):
                    yield tuple(a[:4096].astype(np.int32) for a in arrs)


def main(argv) -> int:
    src = Path(argv[0]) if argv else DEFAULT
    tables = list(luts_from(src))
    print(f"capture: {src.name}")
    print(f"records carrying all three LUTs: {len(tables)}")
    if not tables:
        print("none found")
        return 1

    # how many DISTINCT tables? a per-frame table means it is scene-adaptive
    keys = {tuple(int(x) for x in np.concatenate(t)[::97]) for t in tables}
    print(f"distinct LUT triples: {len(keys)}"
          f"   -> {'scene-ADAPTIVE' if len(keys) > 1 else 'FIXED across frames'}")

    # The FIRST captured triple is the identity, which says nothing. Classify
    # every distinct triple instead, and report the non-identity ones -- those
    # are the only calls that transform anything.
    idx = np.arange(4096)
    seen, distinct = set(), []
    for t in tables:
        k = tuple(int(x) for x in np.concatenate(t)[::97])
        if k not in seen:
            seen.add(k)
            distinct.append(t)
    n_ident = sum(1 for t in distinct if all((p == idx).all() for p in t))
    print(f"\nof {len(distinct)} distinct triples: {n_ident} are the exact "
          f"identity, {len(distinct) - n_ident} transform something")

    nonident = [t for t in distinct if not all((p == idx).all() for p in t)]
    print(f"\n{'#':>3} {'ch':>3} {'[256]':>7} {'[1024]':>7} {'[2048]':>7} "
          f"{'[3072]':>7} {'dir':>14} {'max|delta|':>10}")
    for i, t in enumerate(nonident[:10]):
        for nm, p in zip("RGB", t):
            d = np.diff(p)
            direction = ("decreasing" if (d <= 0).mean() > 0.95 else
                         "increasing" if (d >= 0).mean() > 0.95 else
                         "non-monotone")
            print(f"{i:>3} {nm:>3} {p[256]:7d} {p[1024]:7d} {p[2048]:7d} "
                  f"{p[3072]:7d} {direction:>14} "
                  f"{int(np.abs(p - idx).max()):10d}")

    if not nonident:
        print("\nEvery captured table is the identity: on this capture "
              "area_image_apply_lut transforms NOTHING, so it is not the "
              "invert and this line of evidence is exhausted.")
        return 0

    r, g, b = nonident[0]
    print("\nfirst NON-IDENTITY triple:")
    for nm, t in zip("RGB", (r, g, b)):
        d = np.diff(t)
        direction = ("DECREASING (inverting)" if (d <= 0).mean() > 0.95 else
                     "INCREASING (NOT an inversion)" if (d >= 0).mean() > 0.95
                     else "non-monotone")
        print(f"  {nm}: [0]={t[0]:6d} [1024]={t[1024]:6d} [2048]={t[2048]:6d} "
              f"[4095]={t[4095]:6d}  min={t.min():6d} max={t.max():6d}")
        print(f"     {direction}")

    # Is the table logarithmic? A log invert is linear in log10(index).
    print("\nshape test -- a log invert is LINEAR against log10(index):")
    x = np.arange(1, 4096, dtype=np.float64)
    for nm, t in zip("RGB", (r, g, b)):
        y = t[1:].astype(np.float64)
        m = (y > 0) & (y < y.max())
        if m.sum() < 100:
            print(f"  {nm}: too few usable entries")
            continue
        lx = np.log10(x[m])
        cl = np.corrcoef(x[m], y[m])[0, 1]
        cg = np.corrcoef(lx, y[m])[0, 1]
        slope = np.polyfit(lx, y[m], 1)[0]
        print(f"  {nm}: corr vs index {cl:+.4f}   vs log10(index) {cg:+.4f}"
              f"   slope/decade {slope:8.1f}   -> "
              f"{'LOG' if abs(cg) > abs(cl) else 'LINEAR'}")

    print("\nThis port's invert is rpd = fpo + 1000*(log10(base-c9) - "
          "log10(lin-c9)),")
    print("i.e. slope -1000 per decade. Compare the slopes above: a materially")
    print("different slope means the reconstructed arrangement is wrong, and")
    print("that is exactly the stage docs/74 §158 left as the open suspect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
