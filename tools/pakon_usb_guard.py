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

WHAT THIS MODULE ENFORCES
-------------------------
**No transfer routed through here can write EEPROM 0x52.**

"Routed through here" is load-bearing, not throat-clearing: ``i2c_raw_scan.py``
and the stage-1-loader download (``Fx2.vendor_out``, used by every EEPROM tool
before any guarded call) are NOT routed through here and this module gives
them no protection at all -- see "LIMITS" below before treating this
guarantee as covering the whole codebase.

Stated as what the code does, not as a claim about the hardware: this wrapper
refuses every write-direction request on the device-addressed path, for every
caller, with no override. What the *firmware* would do with a request that
never leaves here is not something this module can demonstrate, and the
docstring no longer pretends otherwise (see "LIMITS" below).

The two chips are not equally precious and the allow-list is built around
exactly that asymmetry:

* ``0x51`` -- FX2 boot personality. **Replaceable**: the vendor ships the
  bytes (``FirmwareLoader/Personalities/USB F135.bin``). Writing it is
  permitted, but only on the boot-personality path and only after an
  explicit, deliberate unlock.
* ``0x52`` -- the per-unit calibration written by the Calibration Wizard. It
  cannot be downloaded, derived, or recreated from any vendor file. **There is
  no unlock for writing it. Not a flag, not an argument, not an environment
  variable.**

  What is actually on it, per ``docs/69`` §4.1/§5.2 rather than from memory:
  the scanner serial (``u32`` at ``0x0F``), ``NegMatrix0..29`` and
  ``PosMatrix`` colour matrices, and -- named by the vendor's own registry
  copy -- ``MotorAdjust``, ``MotorAdjustDrag(_Ir)``, ``MotorSpeedPlus(_Ir)``
  and ``Offset`` per DPI base, ``StepperLens``/``StepperCCD``, and the
  per-mode lamp calibration. The part is **at least 4 Kbit** and the vendor
  keeps two copies of two sections, the highest byte touched being ``0xA24``
  (2596) -- so the "254 of 256 bytes" figure this docstring used to carry was
  wrong, inherited from the 256-byte-device reading ``docs/69`` §5.2 refutes.

THE REQUEST PATHS
-----------------
Recovered from ``TLB.dll`` (md5 ``193d9b2ce0a4b77ae9b78262bd06c0fc``)
``fcn.100160a0`` = ``FN_bEEPromRead`` by static disassembly -- triage-tier
evidence (CLAUDE.md's evidence hierarchy), re-read when this allow-list was
last reviewed but not independently confirmed bit-exact against a live run:

1. **Device-addressed path** -- ``wIndex 0x1234``, and it takes *two*
   requests, not one::

       0x10016138  or eax, 0x50           ; 7-bit addr = 0x50 | index
       0x1001613b  shl eax, 1             ; 8-bit addr (0xA4 for device 2)
       0x10016147  mov byte [var_8h], 0xa2    ; WRITE -> data phase 0xA2
       0x1001614c  je 0x10016158
       0x1001614e  or dword [arg_24h], 1      ; READ  -> select wValue |= 1
       0x10016153  mov byte [var_8h], 0xa9    ; READ  -> data phase 0xA9

   so a chip is selected by ``bRequest 0xA4`` whose ``wValue`` is the 8-bit
   I2C address **with the direction in bit 0**, re-issued before every 32-byte
   chunk; the data phase is then ``0xA9``/``0xA2`` whose ``wValue`` is a flat
   byte offset -- *not* a device address.

   Reads (select with bit 0 set, then ``0xA9``): allowed.
   **Writes -- the even-``wValue`` select and every ``0xA2`` -- never allowed.**

2. **Boot-personality path** -- ``wValue = 0``, ``wIndex = 0``, used by
   ``eeprom_repair.py``. Reads allowed; writes allowed after
   ``unlock_boot_write``.

``0xA0`` (ANCHOR_LOAD_INTERNAL, the FX2 RAM-download route
``i2c_raw_scan.py`` uses to drive raw I2C) is denied: that is the mechanism
the original damage went through.

LIMITS -- what this does NOT yet cover
--------------------------------------
* ``pakon_load.Fx2.vendor_out`` calls ``dev.ctrl_transfer`` directly (line 84)
  to download the stage-1 loader over ``0xA0``. The three EEPROM tools all
  import it, so the ``0xA0`` denial here is a good default but does **not**
  yet close the route that did the original damage. Routing ``Fx2`` through
  this module would.
* Chip selection is firmware-held state (that is what the ``0xA4`` select
  *is*), so which chip a later boot-path request lands on could in principle
  depend on what was selected earlier in the same power cycle -- possibly by
  another process. This module cannot see other processes. Within one, it
  refuses a boot-path write while a non-boot chip was the last one selected.
* ``tools/i2c_raw_scan.py`` still opens its own transfers and bypasses this
  module entirely.
"""
from __future__ import annotations

import contextlib
import os
import sys
import time

# --- request constants (see module docstring for provenance) --------------
VENDOR_IN = 0xC0            # device-to-host, vendor, device
VENDOR_OUT = 0x40           # host-to-device
REQ_READ = 0xA9             # vendor EEPROM read  (wValue = byte offset)
REQ_WRITE = 0xA2            # vendor EEPROM write (wValue = byte offset)
REQ_SELECT = 0xA4           # chip select (wValue = 8-bit I2C addr, bit 0 = read)
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
_selected_device: int | None = None     # last chip selected via 0xA4
_audit: list[str] = []


def device_from_wvalue(wvalue: int) -> int | None:
    """Decode a ``0xA4`` select's ``wValue`` back to a 7-bit address.

    Only meaningful for the select. On ``0xA9``/``0xA2`` the ``wValue`` is a
    flat byte offset (``docs/69`` §5.1) and decoding it as an address would be
    nonsense -- a read at offset 0xA5 is not a request for device 0x52.
    """
    dev = (wvalue >> 1) & 0x7F
    return dev if DEV_MIN <= dev <= DEV_MAX else None


def selected_device() -> int | None:
    """The chip last selected on the device-addressed path, if any."""
    return _selected_device


def unlock_boot_write(reason: str) -> None:
    """Permit writes on the boot-personality path only.

    Deliberately explicit and deliberately narrow. It cannot authorise a write
    to ``0x52``: writes on the device-addressed path are refused
    unconditionally regardless of this flag.

    Process-global, and it stays set. Use :func:`boot_write_unlocked` to scope
    it, or :func:`lock_boot_write` to put it back.
    """
    global _boot_write_unlocked
    _boot_write_unlocked = True
    _log(f"BOOT-WRITE UNLOCKED: {reason}")


def lock_boot_write() -> None:
    """Re-arm the boot-write gate."""
    global _boot_write_unlocked
    _boot_write_unlocked = False
    _log("boot-write re-locked")


@contextlib.contextmanager
def boot_write_unlocked(reason: str):
    """``with`` form of :func:`unlock_boot_write`, scoped to the block."""
    prior = _boot_write_unlocked
    unlock_boot_write(reason)
    try:
        yield
    finally:
        if not prior:
            lock_boot_write()


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
    global _selected_device

    where = (f"bRequest=0x{b_request:02X} wValue=0x{wvalue:04X} "
             f"wIndex=0x{windex:04X}")
    if _selected_device is not None:
        where += f" [selected 0x{_selected_device:02X}]"

    # bmRequestType's bit 7 is the authoritative direction (USB spec); is_write
    # is supposed to be derived from it (see ctrl_transfer below). A caller
    # that passes the two inconsistently gets refused here rather than judged
    # on whichever one happens to be wrong -- this parameter exists for that
    # cross-check, not just to be threaded through unused.
    bmrt_is_write = not (bm_request_type & 0x80)
    if bmrt_is_write != is_write:
        _log(f"DENIED (bmRequestType/is_write mismatch, "
             f"bmRequestType=0x{bm_request_type:02X}): {where}")
        raise TransferDenied(
            f"bmRequestType=0x{bm_request_type:02X} direction bit disagrees "
            f"with is_write={is_write}: {where}")

    # --- the hard rule: no write-direction traffic on the device path -----
    # 0xA4 is host-to-device but is a *select*, not a data phase, so it is
    # judged on its own terms just below rather than swept up here.
    if is_write and windex == WINDEX_DEVICE and b_request != REQ_SELECT:
        _log(f"DENIED (no writes on the device-addressed path): {where}")
        raise TransferDenied(
            "refusing a write on the device-addressed path (wIndex 0x1234). "
            "This is the only route that reaches EEPROM 0x52, so this "
            "wrapper keeps it read-only for every caller -- including after "
            "unlock_boot_write().")

    # --- the chip select: direction lives in bit 0 of wValue --------------
    if b_request == REQ_SELECT:
        dev = device_from_wvalue(wvalue)
        if windex != WINDEX_DEVICE or dev is None:
            _log(f"DENIED (malformed chip select): {where}")
            raise TransferDenied(
                f"chip select not on the allow-list: {where}. Expected "
                f"wIndex 0x1234 and wValue ((n|0x50)<<1)|1, n <= 7.")
        if not wvalue & 1:
            # `or dword [arg_24h], 1` at 0x1001614e sets bit 0 for reads
            # only, so an even select is the opening half of a write.
            _log(f"DENIED (write-direction chip select, device "
                 f"0x{dev:02X}): {where}")
            raise TransferDenied(
                f"refusing a write-direction chip select for device "
                f"0x{dev:02X} (wValue bit 0 clear). Only the read-direction "
                f"select is permitted.")
        _selected_device = dev
        _log(f"allow chip select for read, device 0x{dev:02X}: {where}")
        return

    # --- the raw-I2C route that caused the original damage ----------------
    if b_request == REQ_ANCHOR_LOAD:
        _log(f"DENIED (FX2 RAM-download / raw-I2C route): {where}")
        raise TransferDenied(
            "refusing bRequest 0xA0 (ANCHOR_LOAD_INTERNAL). This is the "
            "route the blind write sweep used to corrupt the boot EEPROM.")

    # --- reads ------------------------------------------------------------
    # Allowed on (bRequest, wIndex) alone: on 0xA9 the wValue is a byte
    # offset, so there is no device to decode and nothing to match it against.
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
        if _selected_device is not None and _selected_device != DEV_BOOT:
            # Selection is firmware state. Whether it survives into the
            # boot path is not established either way, so refuse rather
            # than find out on the irreplaceable chip.
            _log(f"DENIED (boot write while 0x{_selected_device:02X} was "
                 f"last selected): {where}")
            raise TransferDenied(
                f"refusing a boot-personality write while device "
                f"0x{_selected_device:02X} was the last chip selected. Chip "
                f"selection is firmware-held state and this module cannot "
                f"show it does not carry into the boot path.")
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
