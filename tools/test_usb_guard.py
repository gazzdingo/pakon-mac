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


def denied(bmrt, req, wval, widx, what):
    try:
        G.check(bmrt, req, wval, widx)
        ok(False, what + "  (was ALLOWED)")
    except G.TransferDenied:
        ok(True, what)


def allowed(bmrt, req, wval, widx, what):
    try:
        G.check(bmrt, req, wval, widx)
        ok(True, what)
    except G.TransferDenied as e:
        ok(False, what + f"  (denied: {e})")


def sel(dev, read):
    """The vendor's own select encoding: 8-bit I2C address, bit 0 = read.

    ``0x10016138: or eax,0x50`` / ``0x1001613b: shl eax,1`` / ``0x1001614e:
    or dword [arg_24h], 1`` (read only) in TLB.dll ``fcn.100160a0``.
    """
    return (dev << 1) | (1 if read else 0)


def reset():
    """Clear the guard's firmware-selection state between groups."""
    G._selected_device = None


# The sequence the OEM itself issues, transcribed from docs/69 sec5.1 rather
# than from this module's own encoding -- the whole point of having it here is
# that it is an INDEPENDENT input. The previous version of these tests built
# every case from the module's own helper, so they confirmed the intended
# policy and would have passed whether or not it matched the real device.
print("the OEM's own read sequence passes end to end")
reset()
allowed(G.VENDOR_OUT, 0xA4, 0x00A5, 0x1234,
        "0xA4 select of device 2 for read (wValue 0x00A5)")
ok(G.selected_device() == 0x52, "the select is recorded as device 0x52")
for off in (0x000, 0x400, 0x800, 0xA00, 0xA24 - 32):
    allowed(G.VENDOR_IN, 0xA9, off, 0x1234,
            f"0xA9 data phase at byte offset 0x{off:03X}")

print("\na chip select must be host-to-device, not just wValue-shaped right")
reset()
denied(G.VENDOR_IN, G.REQ_SELECT, sel(0x52, True), G.WINDEX_DEVICE,
       "an IN-direction 0xA4 is refused even with a read-shaped wValue")
ok(G.selected_device() is None,
   "and does NOT get recorded as a selection")

print("\nthe irreplaceable chip can never be written")
reset()
denied(G.VENDOR_OUT, G.REQ_WRITE, 0x000, G.WINDEX_DEVICE,
       "0xA2 data phase on the device path is refused")
denied(G.VENDOR_OUT, G.REQ_SELECT, sel(0x52, False), G.WINDEX_DEVICE,
       "the write-direction select for 0x52 is refused (bit 0 clear)")
G.unlock_boot_write("test: prove the unlock cannot reach the device path")
denied(G.VENDOR_OUT, G.REQ_WRITE, 0x000, G.WINDEX_DEVICE,
       "still refused AFTER unlock_boot_write() -- no override exists")
denied(G.VENDOR_OUT, G.REQ_SELECT, sel(0x52, False), G.WINDEX_DEVICE,
       "write-direction select still refused after unlock")
G.lock_boot_write()

print("\nno write-direction traffic at all on the device-addressed path")
for d in range(G.DEV_MIN, G.DEV_MAX + 1):
    denied(G.VENDOR_OUT, G.REQ_SELECT, sel(d, False), G.WINDEX_DEVICE,
           f"write-direction select for device 0x{d:02X} refused")
denied(G.VENDOR_OUT, G.REQ_SELECT, sel(0x52, True), G.WINDEX_BOOT,
       "a select is refused off its own index (wIndex 0)")
denied(G.VENDOR_OUT, G.REQ_SELECT, 0x00FF, G.WINDEX_DEVICE,
       "a select outside 0x50-0x57 is refused")

print("\nthe raw-I2C route that caused the original damage")
denied(G.VENDOR_OUT, G.REQ_ANCHOR_LOAD, 0, 0,
       "bRequest 0xA0 (FX2 RAM download) refused")
denied(G.VENDOR_IN, G.REQ_ANCHOR_LOAD, 0, 0,
       "0xA0 refused for reads as well")

print("\nreads the dumpers actually need still work")
reset()
for d in range(G.DEV_MIN, G.DEV_MAX + 1):
    allowed(G.VENDOR_OUT, G.REQ_SELECT, sel(d, True), G.WINDEX_DEVICE,
            f"read-direction select of device 0x{d:02X} allowed")
allowed(G.VENDOR_IN, G.REQ_READ, 0, G.WINDEX_DEVICE,
        "device-path read allowed")
allowed(G.VENDOR_IN, G.REQ_READ, 0, G.WINDEX_BOOT,
        "boot-personality read allowed (eeprom_repair's verify path)")

print("\nboot-personality write: gated, THEN permitted")
reset()
G.lock_boot_write()
denied(G.VENDOR_OUT, G.REQ_WRITE, 0, G.WINDEX_BOOT,
       "refused BEFORE unlock (the gate half, previously untested)")
with G.boot_write_unlocked("test: scoped unlock"):
    allowed(G.VENDOR_OUT, G.REQ_WRITE, 0, G.WINDEX_BOOT,
            "allowed inside the unlock (0x51 -- the vendor ships the bytes)")
denied(G.VENDOR_OUT, G.REQ_WRITE, 0, G.WINDEX_BOOT,
       "re-locked on leaving the context manager")

print("\nselection state cannot leak a boot write onto another chip")
G.unlock_boot_write("test: selection interlock is independent of the unlock")
allowed(G.VENDOR_OUT, G.REQ_SELECT, sel(0x52, True), G.WINDEX_DEVICE,
        "select 0x52 for reading")
denied(G.VENDOR_OUT, G.REQ_WRITE, 0, G.WINDEX_BOOT,
       "boot write refused while 0x52 was the last chip selected")
allowed(G.VENDOR_OUT, G.REQ_SELECT, sel(0x51, True), G.WINDEX_DEVICE,
        "select 0x51")
allowed(G.VENDOR_OUT, G.REQ_WRITE, 0, G.WINDEX_BOOT,
        "boot write allowed again once 0x51 is the selected chip")
G.lock_boot_write()

print("\nunrecognised traffic is dropped, not passed through")
denied(G.VENDOR_IN, 0xB7, 0, G.WINDEX_DEVICE,
       "unknown read bRequest refused")
denied(G.VENDOR_OUT, G.REQ_WRITE, 0x9999, 0x4321,
       "unknown write refused")

print(f"\n{PASS}/{PASS + FAIL} checks passed")
sys.exit(0 if FAIL == 0 else 1)
