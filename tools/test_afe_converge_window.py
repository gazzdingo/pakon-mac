#!/usr/bin/env python3
"""The convergence window must reject what §91.3 wrongly accepted.

The original bug was not subtle and was not caught: `converge_afe_offsets`
tested `landed` against BLACK_MIN_WIRE..BLACK_MAX_WIRE (400..4000), a band so
wide it contains both the vendor's black level (~638) and this port's lifted
one (~1659). Round 1 therefore "landed" on the seed and returned it unchanged
-- on real hardware, silently, reporting success.

No test caught that because no test asserted the window could *discriminate*.
These do, using the real measured levels from docs/74 §91/§92 rather than
invented ones.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_calibration as bcal          # noqa: E402

PASS = FAIL = 0


def ok(cond, what):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok    {what}")
    else:
        FAIL += 1
        print(f"  FAIL  {what}")


def landed(black):
    """The predicate converge_afe_offsets uses, in one place."""
    return all(bcal.BLACK_CONVERGE_MIN_WIRE <= v <= bcal.BLACK_CONVERGE_MAX_WIRE
               for v in black)


# Real measurements, tools/afe_black_probe.py on serial 16275, docs/74 §92.
VENDOR_BLACK = [779.7, 562.3, 571.2]     # at the vendor's own (-19,-26,-19)
STORED_BLACK = [1747.9, 1590.8, 1639.6]  # at the then-stored (0,-6,2)

print("the window must discriminate -- this is the bug §91.3 shipped")
ok(landed(VENDOR_BLACK),
   "the vendor's OWN converged black is accepted (else we reject the target)")
ok(not landed(STORED_BLACK),
   "the lifted black this port had is REJECTED (the old window accepted it)")

print("\nthe old safety band could not tell them apart")
old = lambda b: all(bcal.BLACK_MIN_WIRE <= v <= bcal.BLACK_MAX_WIRE for v in b)
ok(old(VENDOR_BLACK) and old(STORED_BLACK),
   "400..4000 accepts BOTH -- documents why the loop returned its seed")

print("\nthe safety band itself is unchanged (other callers depend on it)")
ok(bcal.BLACK_MIN_WIRE == 400.0 and bcal.BLACK_MAX_WIRE == 4000.0,
   "BLACK_MIN_WIRE/BLACK_MAX_WIRE still 400/4000")
ok(bcal.BLACK_TARGET_WIRE == 1300.0,
   "BLACK_TARGET_WIRE still 1300 (build_calibration/calib_wizard/test_calib)")

print("\nthe convergence target is the measured vendor level")
ok(abs(bcal.BLACK_CONVERGE_TARGET_WIRE - 637.7) < 1.0,
   f"BLACK_CONVERGE_TARGET_WIRE = {bcal.BLACK_CONVERGE_TARGET_WIRE} "
   f"(measured 637.7)")
ok(bcal.BLACK_CONVERGE_MIN_WIRE <= min(VENDOR_BLACK)
   and max(VENDOR_BLACK) <= bcal.BLACK_CONVERGE_MAX_WIRE,
   "the window spans the vendor's 217-code inter-channel spread")

print("\nthe seed must never satisfy the window by accident")
# LIVE_AFE_SEED is (10,10,10); its black is whatever the sensor gives, but the
# point is that a *correction* must be possible. A window that accepts a
# 1000-code error cannot converge anything.
ok(not landed([1659.4, 1659.4, 1659.4]),
   "a uniform 1659 (this port's measured mean) is rejected")
ok(not landed([1300.0, 1300.0, 1300.0]),
   "even BLACK_TARGET_WIRE itself is rejected as a converged state")

print(f"\n{PASS}/{PASS + FAIL} checks passed")
sys.exit(0 if FAIL == 0 else 1)
