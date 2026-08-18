#!/usr/bin/env python3
"""The allow-list's guarantees, proven rather than asserted.

Runs with no hardware attached: `check()` is deliberately separate from the
transfer itself so the policy can be exercised directly.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["PAKON_USB_GUARD_QUIET"] = "1"

import pakon_usb_guard as G

PASS = FAIL = 0


def ok(cond, what):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok    {what}")
    else:
        FAIL += 1
        print(f"  FAIL  {what}")


def denied(bmrt, req, wval, widx, is_write, what):
    try:
        G.check(bmrt, req, wval, widx, is_write)
        ok(False, what + "  (was ALLOWED)")
    except G.TransferDenied:
        ok(True, what)


def allowed(bmrt, req, wval, widx, is_write, what):
    try:
        G.check(bmrt, req, wval, widx, is_write)
        ok(True, what)
    except G.TransferDenied as e:
        ok(False, what + f"  (denied: {e})")


def wv(dev, read):
    """The vendor's own encoding: ((n | 0x50) << 1) | readBit."""
    return (dev << 1) | (1 if read else 0)


print("the irreplaceable chip can never be written")
denied(G.VENDOR_OUT, G.REQ_WRITE, wv(0x52, False), G.WINDEX_DEVICE, True,
       "write to EEPROM 0x52 is refused")
G.unlock_boot_write("test: prove the unlock cannot reach 0x52")
denied(G.VENDOR_OUT, G.REQ_WRITE, wv(0x52, False), G.WINDEX_DEVICE, True,
       "still refused AFTER unlock_boot_write() -- no override exists")
denied(G.VENDOR_OUT, G.REQ_WRITE, wv(0x52, True), G.WINDEX_DEVICE, True,
       "refused with the read bit set too (encoding cannot smuggle it)")

print("\nno writes at all on the device-addressed path")
for d in range(G.DEV_MIN, G.DEV_MAX + 1):
    denied(G.VENDOR_OUT, G.REQ_WRITE, wv(d, False), G.WINDEX_DEVICE, True,
           f"write to device 0x{d:02X} refused")

print("\nthe raw-I2C route that caused the original damage")
denied(G.VENDOR_OUT, G.REQ_ANCHOR_LOAD, 0, 0, True,
       "bRequest 0xA0 (FX2 RAM download) refused")
denied(G.VENDOR_IN, G.REQ_ANCHOR_LOAD, 0, 0, False,
       "0xA0 refused for reads as well")

print("\nreads the dumpers actually need still work")
for d in range(G.DEV_MIN, G.DEV_MAX + 1):
    allowed(G.VENDOR_IN, G.REQ_READ, wv(d, True), G.WINDEX_DEVICE, False,
            f"read device 0x{d:02X} allowed")
allowed(G.VENDOR_IN, G.REQ_READ, 0, G.WINDEX_BOOT, False,
        "boot-personality read allowed (eeprom_repair's verify path)")

print("\nboot-personality write: gated, then permitted")
allowed(G.VENDOR_OUT, G.REQ_WRITE, 0, G.WINDEX_BOOT, True,
        "allowed after unlock (0x51 is replaceable -- vendor ships the bytes)")

print("\nunrecognised traffic is dropped, not passed through")
denied(G.VENDOR_IN, 0xB7, 0, G.WINDEX_DEVICE, False,
       "unknown read bRequest refused")
denied(G.VENDOR_OUT, G.REQ_WRITE, 0x9999, 0x4321, True,
       "unknown write refused")

print(f"\n{PASS}/{PASS + FAIL} checks passed")
sys.exit(0 if FAIL == 0 else 1)
