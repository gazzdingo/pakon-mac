#!/usr/bin/env python3
"""Transport-level allow-list for every EEPROM/I2C control transfer.

WHY THIS EXISTS
---------------
This project already destroyed one EEPROM. ``backups/eeprom-i2c/README.md``
and ``tools/eeprom_repair.py`` record it:

    healthy (Kodak USB F135.bin)   c0 05 0f 35 f2 07 aa 04 02
    after a blind I2C write sweep  5c 05 0f 35 f2 07 aa 04

A sweep of blind writes across what were assumed to be board addresses -- but
were in fact I2C *device* addresses -- overwrote byte 0 of the FX2 boot
personality. ``0xC0`` is the format signature meaning "take VID/PID from this
EEPROM"; ``0x5C`` is not valid, so the scanner stopped identifying itself.

That was recoverable only because Kodak ships the exact replacement bytes
(``FirmwareLoader/Personalities/USB F135.bin``). **The other chip has no such
escape.**

The idea is borrowed from ``pablonavarrob/pakon-tlx-macos``, which puts its
safety in the transport rather than in each caller: on ``wIndex 0x1234`` only
known reads are allowed through, anything else is dropped and logged. That is
a guardrail; per-tool discipline is only a rule, and this repo has already
demonstrated the difference. ``tools/i2c_raw_scan.py`` and
``i2c_eeprom.hex.DANGEROUS-WRITES`` still sit in the same directory as the
read-only dumpers, and nothing structural stops the wrong one being run.

THE ONE GUARANTEE THIS MODULE MAKES
-----------------------------------
**Nothing routed through here can ever write EEPROM 0x52.**

The two chips are not equally precious and the allow-list is built around
exactly that asymmetry:

* ``0x51`` -- FX2 boot personality. **Replaceable**: the vendor ships the
  bytes. Writing it is permitted, but only on the boot-personality path and
  only after an explicit, deliberate unlock.
* ``0x52`` -- the per-unit optical/motor calibration. 254/256 bytes of
  magnification, optical alignment and per-format motor speeds describing
  *this individual scanner*. The F-135 Service Manual is explicit that the
  Calibration Wizard writes all calibration data here. It cannot be
  downloaded, derived, or recreated from any vendor file. **There is no
  unlock for writing it. Not a flag, not an argument, not an environment
  variable.**

THE TWO REQUEST PATHS, AND WHY THE RULE IS CLEAN
------------------------------------------------
Recovered from ``TLB.dll`` ``fcn.10015d80`` (IOCTL 0x222059) and confirmed by
the tools that already work:

1. **Device-addressed path** -- ``wIndex 0x1234``,
   ``wValue = ((n | 0x50) << 1) | readBit``. This is the only way to reach a
   specific EEPROM, and therefore the only way to reach ``0x52``.
   Reads: allowed. **Writes: never allowed, by any caller.**
2. **Boot-personality path** -- ``wValue = 0``, ``wIndex = 0``, used by
   ``eeprom_repair.py``. This reaches the FX2 boot EEPROM only, which is the
   replaceable one. Reads allowed; writes allowed after ``unlock_boot_write``.

Because ``0x52`` is only reachable via path 1, and path 1 is read-only, the
guarantee above holds structurally rather than by inspection of each caller.

``0xA0`` (ANCHOR_LOAD_INTERNAL, the FX2 RAM-download route ``i2c_raw_scan.py``
uses to drive raw I2C) is denied by default: that is the mechanism the
original damage went through.
"""
from __future__ import annotations

import os
import sys
import time

# --- request constants (see module docstring for provenance) --------------
VENDOR_IN = 0xC0            # device-to-host, vendor, device
VENDOR_OUT = 0x40           # host-to-device
REQ_READ = 0xA9             # vendor EEPROM read
REQ_WRITE = 0xA2            # vendor EEPROM write
REQ_ANCHOR_LOAD = 0xA0      # FX2 RAM download (raw-I2C route)

WINDEX_DEVICE = 0x1234      # device-addressed path
WINDEX_BOOT = 0x0000        # boot-personality path

# 7-bit I2C serial-EEPROM range the wValue encoding can express
DEV_MIN, DEV_MAX = 0x50, 0x57
DEV_BOOT = 0x51             # FX2 boot personality -- replaceable
DEV_CALIBRATION = 0x52      # per-unit calibration -- IRREPLACEABLE


class TransferDenied(RuntimeError):
    """A control transfer was refused by the allow-list."""


_boot_write_unlocked = False
_audit: list[str] = []


def device_from_wvalue(wvalue: int) -> int | None:
    """Decode ``((n | 0x50) << 1) | readBit`` back to a 7-bit address."""
    dev = (wvalue >> 1) & 0x7F
    return dev if DEV_MIN <= dev <= DEV_MAX else None


def unlock_boot_write(reason: str) -> None:
    """Permit writes on the boot-personality path only.

    Deliberately explicit and deliberately narrow. This cannot authorise a
    write to ``0x52``: that chip is only reachable on the device-addressed
    path, where writes are refused unconditionally regardless of this flag.
    """
    global _boot_write_unlocked
    _boot_write_unlocked = True
    _log(f"BOOT-WRITE UNLOCKED: {reason}")


def audit_log() -> list[str]:
    return list(_audit)


def _log(msg: str) -> None:
    line = f"[usb-guard {time.strftime('%H:%M:%S')}] {msg}"
    _audit.append(line)
    if os.environ.get("PAKON_USB_GUARD_QUIET") != "1":
        print(line, file=sys.stderr)


def check(bm_request_type: int, b_request: int, wvalue: int, windex: int,
          is_write: bool) -> None:
    """Raise ``TransferDenied`` unless this exact transfer is allow-listed.

    Separated from :func:`ctrl_transfer` so it can be unit-tested without a
    device attached -- see ``tools/test_usb_guard.py``.
    """
    dev = device_from_wvalue(wvalue)
    where = (f"bRequest=0x{b_request:02X} wValue=0x{wvalue:04X} "
             f"wIndex=0x{windex:04X}"
             + (f" (device 0x{dev:02X})" if dev is not None else ""))

    # --- the hard guarantee, checked first and unconditionally ------------
    if is_write and windex == WINDEX_DEVICE:
        if dev == DEV_CALIBRATION:
            _log(f"DENIED (irreplaceable calibration EEPROM): {where}")
            raise TransferDenied(
                "refusing to write EEPROM 0x52 -- the per-unit calibration "
                "cannot be recreated from any vendor file. There is no "
                "override for this.")
        _log(f"DENIED (no writes on the device-addressed path): {where}")
        raise TransferDenied(
            "refusing a write on the device-addressed path (wIndex 0x1234). "
            "This is the only route that can reach EEPROM 0x52, so it is "
            "read-only for every caller.")

    # --- the raw-I2C route that caused the original damage ----------------
    if b_request == REQ_ANCHOR_LOAD:
        _log(f"DENIED (FX2 RAM-download / raw-I2C route): {where}")
        raise TransferDenied(
            "refusing bRequest 0xA0 (ANCHOR_LOAD_INTERNAL). This is the "
            "route the blind write sweep used to corrupt the boot EEPROM.")

    # --- reads --------------------------------------------------------------
    if not is_write:
        if b_request == REQ_READ and windex in (WINDEX_DEVICE, WINDEX_BOOT):
            _log(f"allow read: {where}")
            return
        _log(f"DENIED (unrecognised read): {where}")
        raise TransferDenied(
            f"read not on the allow-list: {where}. Only bRequest 0xA9 on "
            f"wIndex 0x1234 or 0x0000 is permitted.")

    # --- writes on the boot-personality path only -------------------------
    if b_request == REQ_WRITE and windex == WINDEX_BOOT and wvalue == 0:
        if not _boot_write_unlocked:
            _log(f"DENIED (boot write not unlocked): {where}")
            raise TransferDenied(
                "boot-personality write refused: call unlock_boot_write() "
                "first. (Even unlocked, this cannot reach EEPROM 0x52.)")
        _log(f"allow boot write (unlocked): {where}")
        return

    _log(f"DENIED (unrecognised write): {where}")
    raise TransferDenied(f"write not on the allow-list: {where}")


def ctrl_transfer(dev, bm_request_type: int, b_request: int, wvalue: int,
                  windex: int, data_or_length, timeout: int | None = None):
    """``dev.ctrl_transfer`` with the allow-list in front of it."""
    is_write = not (bm_request_type & 0x80)
    check(bm_request_type, b_request, wvalue, windex, is_write)
    return dev.ctrl_transfer(bm_request_type, b_request, wvalue, windex,
                             data_or_length, timeout)
