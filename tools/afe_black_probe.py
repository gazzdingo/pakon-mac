#!/usr/bin/env python3
"""Measure the black level the vendor's own AFE offsets actually produce.

WHY THIS EXISTS
---------------
docs/74 §91 recovered the vendor's live convergence from the v28 capture: it
seeds at ``(10, 10, 10)`` -- identical to this port's ``LIVE_AFE_SEED`` -- and
settles at ``(-19, -26, -19)`` in four rounds.

This port's own loop returned the seed **unchanged**, because
``converge_afe_offsets`` accepts any black level in ``BLACK_MIN_WIRE`` (400)
.. ``BLACK_MAX_WIRE`` (4000) as "landed" -- a 10x band around a target of
1300 -- so round 1 terminates before a correction is ever applied.

Tightening that window needs a NUMBER, not a guess. And hardcoding
``(-19, -26, -19)`` is not acceptable: those are *this unit's* offsets. Any
other F-135 has its own sensor and must converge to its own. What generalises
is the TARGET BLACK LEVEL the vendor aims at -- measurable here, because we
know the offsets the vendor chose for this unit.

So: read the black level at the offsets currently stored, and at the offsets
the vendor converged to. The second is the vendor's target, in wire units, on
real silicon.

WHAT THIS SENDS, EXACTLY
------------------------
Per round, via ``pakon_scan._live_afe_measure``:

  * ``ccd_configure`` with the probe offsets. Its docstring: "exactly the
    registers an ordinary scan writes, so nothing here is a new write path;
    only the offsets vary between rounds."
  * ``reset_fifos`` x2, ``acquire``
  * read until 2000 lines (24 MB at 12000 B/line), decoded with the same
    ``find_phase``/``split_lines`` every real scan uses.

And, per that same docstring: **"Never sends TRANSPORT FORWARD and never
touches the lamp."** No motor. No lamp. Bounded at 15 s per round with a 3 s
stall abort, so worst case for the whole run is ~30 s -- not the 353 s
full-scan path ``run --live-afe-converge`` takes. That is a different entry
point and is NOT used here.

WHAT THIS DOES NOT DO
---------------------
  * does not move the motor or light the lamp (see above)
  * does not write any EEPROM
  * does not write ``calibration/`` -- it prints, and that is all
  * does not promote anything anywhere

STATE IT LEAVES BEHIND
----------------------
A probe leaves the AFE offset registers at whatever it last wrote, so this
restores the stored offsets in a ``finally`` block -- including on Ctrl-C or
an exception. The first round is deliberately the STORED offsets, so the
opening write is a no-op rather than a jump.

SAFETY PRECONDITION: the lamp must already be off. This does not turn it on
and does not turn it off. If unsure, run ``python3 tools/pakon_scan.py stop``
first.
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import replace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_calibration as bcal             # noqa: E402
import pakon_scan as ps                      # noqa: E402

#: docs/74 §91: what the vendor converged to on THIS unit (serial 16275).
#: A probe point for learning the vendor's target black level -- NOT a value
#: to adopt. Another scanner converges somewhere else, which is the point.
VENDOR_CONVERGED = (-19, -26, -19)


def _log(event, **kw):
    if event in ("warn", "error"):
        print(f"  ! {event}: {kw}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--probe-bytes", type=int, default=ps.LIVE_AFE_PROBE_BYTES,
                    help="bytes per round (default %(default)s = 2000 lines)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would be sent, touch nothing, exit")
    args = ap.parse_args()

    cfg = ps.ScanConfig.from_calibration()
    stored = tuple(int(v) for v in cfg.afe_offsets)
    points = [("stored (calibration/README.json)", stored),
              ("vendor-converged (docs/74 s91)", VENDOR_CONVERGED)]

    print("AFE black-level probe -- read only, no lamp, no motor, no writes")
    print(f"  stored offsets   : {stored}")
    print(f"  vendor converged : {VENDOR_CONVERGED}")
    print(f"  bytes per round  : {args.probe_bytes} "
          f"({args.probe_bytes // 12000} lines)")
    print(f"  rounds           : {len(points)} (<=15 s each, 3 s stall abort)")
    print(f"  target in code   : BLACK_TARGET_WIRE = {bcal.BLACK_TARGET_WIRE}")
    print(f"  accept window    : {bcal.BLACK_MIN_WIRE} .. "
          f"{bcal.BLACK_MAX_WIRE}  <- the 10x band that ends round 1 early")
    if args.dry_run:
        print("\n--dry-run: nothing sent.")
        return 0

    link = ps.Link.open()
    results = []
    try:
        link.clear_fault()
        for label, off in points:
            print(f"\nprobing {label}: offsets {off}")
            cap = ps._live_afe_measure(link, cfg, off, args.probe_bytes, _log)
            black = [float(v) for v in cap.channel_means()]
            floored = cap.is_floored()
            results.append((label, off, black, floored))
            print(f"  black per channel : "
                  f"{black[0]:.1f}  {black[1]:.1f}  {black[2]:.1f}")
            print(f"  mean              : {sum(black) / 3.0:.1f}")
            print(f"  floored           : {floored}"
                  + ("   <- at the rail; a censored reading, not a level"
                     if floored else ""))
    finally:
        # Always put the scanner back, even on Ctrl-C or an exception.
        try:
            ps.ccd_configure(link, replace(cfg, afe_offsets=stored))
            print(f"\nrestored stored offsets {stored}")
        except Exception as exc:                       # noqa: BLE001
            print(f"\n!! COULD NOT RESTORE offsets {stored}: {exc}")
            print("!! run: python3 tools/pakon_scan.py stop")

    if len(results) == 2:
        _, _, b_stored, f_stored = results[0]
        _, _, b_vendor, f_vendor = results[1]
        print("\n--- what this tells us ---")
        if f_stored or f_vendor:
            print("  a reading was floored, so this is not usable as a "
                  "target. Report it and stop; do not fit to a rail.")
            return 1
        ms, mv = sum(b_stored) / 3.0, sum(b_vendor) / 3.0
        print(f"  black at stored {stored}: {ms:.1f}")
        print(f"  black at vendor {VENDOR_CONVERGED}: {mv:.1f}")
        print(f"  difference: {ms - mv:+.1f} wire codes")
        print(f"\n  the vendor's target black level is ~{mv:.0f}, against "
              f"BLACK_TARGET_WIRE = {bcal.BLACK_TARGET_WIRE:.0f} in code.")
        print("  NOTHING is written from this. What to do with it is a "
              "separate, reviewed change.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
