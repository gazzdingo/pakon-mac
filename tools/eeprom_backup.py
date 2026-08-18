#!/usr/bin/env python3
"""Back up every EEPROM, using the stage-1 loader and the vendor's sequence.

This project has now got the parameters wrong TWICE, in opposite directions,
and both times the tool reported success.

1. `pakon_load.py` issued 0xA9 with wValue=0, wIndex=0 and treated the result
   as a "personality" blob. Not addressing any EEPROM.

2. This tool then sent 0xA9 with `((n | 0x50) << 1) | 1` in wValue and no
   chip select at all, believing that was what fcn.100160a0 does. Issue #50:
   run against a live F-135+, it returned 0xFF for 8192 of 8192 bytes, on both
   chips, with no error -- a bus-idle read written out as a backup file.

THE SEQUENCE THE VENDOR ACTUALLY USES (docs/69 §5.1, read from TLB.dll
md5 193d9b2ce0a4b77ae9b78262bd06c0fc, fcn.100160a0 -- disassembly, triage-tier
evidence, not yet run bit-exact against this project's own hardware):

    0x10016138  or eax, 0x50            ; 7-bit addr = 0x50 | index
    0x1001613b  shl eax, 1              ; 8-bit addr  -> 0xA4 for index 2
    0x1001614e  or dword [arg_24h], 1   ; READ sets bit 0 -> 0xA5
    0x10016153  mov byte [var_8h], 0xa9 ; then the data phase

so it is TWO requests per chunk, not one:

    select   bRequest 0xA4   wValue ((n|0x50)<<1)|1   wIndex 0x1234  len 0
    data     bRequest 0xA9   wValue = flat BYTE OFFSET wIndex 0x1234  <=32B

The select is re-issued before EVERY chunk (the loop at 0x10016164). `wValue`
on the data phase is a byte offset, NOT an address -- that was the whole of
bug 2.

WHAT IS SAVED. Nothing is written to the scanner, ever. A dump is only saved
if `pakon_eeprom_check.py` can verify at least one section header + CRC-32; a
read that addresses nothing now fails loudly instead of producing a file that
looks like a backup. Use --force to keep a failing read for diagnosis; it is
named .SUSPECT and is not a backup.

STATUS: the sequence is read from disassembly (docs/69 §5.1) -- triage-tier
evidence, not a bit-exact confirmation -- and matches a third-party live read
on another unit (issue #50), but has NOT yet been run against this project's
own scanner. The validation above is what makes that acceptable -- a wrong
read can no longer masquerade as a good one.

Run it with the scanner power-cycled and NOT yet loaded (04b4:8613).
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time

import usb.core
import usb.util

# This file lives in tools/ alongside these three, so a direct run finds them
# via Python's own script-directory auto-insert -- but that only holds true
# for a direct run. The explicit insert makes it hold for an import too.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pakon_eeprom_check as check          # noqa: E402
import pakon_usb_guard as guard             # noqa: E402
from pakon_load import Fx2, HexImage, find_unloaded   # noqa: E402

# Protocol constants live in pakon_usb_guard, not redefined here: this file
# got the vendor's parameters wrong twice already (see the module docstring
# above), and a second, independently-hardcoded copy is exactly how a future
# correction to one and not the other goes unnoticed by the allow-list.
VENDOR_IN = guard.VENDOR_IN
VENDOR_OUT = guard.VENDOR_OUT
SELECT = guard.REQ_SELECT
READ = guard.REQ_READ
WINDEX = guard.WINDEX_DEVICE
CHUNK = 32                  # the vendor's own chunk size (0x1001618e: cmp esi, 0x20)


def select_chip(dev, n, timeout=4000) -> None:
    """Issue the read-direction chip select. Bit 0 set == read (0x1001614e)."""
    guard.ctrl_transfer(dev, VENDOR_OUT, SELECT, ((n | 0x50) << 1) | 1,
                        WINDEX, b"", timeout)


class PartialRead(bytes):
    """A read that stopped early because of a real USB error, not a clean
    short read. Distinct from `bytes` in identity only, so a caller that
    forgets to check for it still gets the (possibly incomplete) data rather
    than a crash -- but callers that DO check can tell "the vendor's own
    section headers say this is complete" apart from "a transient error cut
    this off, whatever bytes happen to be in it may end mid-section"."""
    error: str = ""


def read_one(dev, n, length, timeout=4000):
    """Read `length` bytes from device index `n`, the way the vendor does.

    Select then data phase, in 32-byte chunks, select re-issued before each --
    matching the loop at 0x10016164 rather than approximating it.
    """
    out = bytearray()
    try:
        for off in range(0, length, CHUNK):
            want = min(CHUNK, length - off)
            select_chip(dev, n, timeout)
            got = bytes(guard.ctrl_transfer(dev, VENDOR_IN, READ, off,
                                            WINDEX, want, timeout))
            out += got
            if len(got) < want:            # short read: stop, don't pad
                break
    except usb.core.USBError as exc:
        if not out:
            return f"ERROR: {exc}"
        partial = PartialRead(bytes(out))
        partial.error = str(exc)
        return partial
    return bytes(out)


# The vendor's own protocol bound (0x100160bc: cmp eax, 0x2000) -- a real
# section's length field is always small (398 or 36 healthy, but even a
# short/corrupted primary is still a plausible small value; a real live read
# saw 346 -- docs/69, live run 2026-08-18). Junk reads decode to a length
# field far outside this: the FX2 boot personality read back as length
# 0x350F05C0, the unpopulated-address ramp (00 01 02 03...) as 0x03020100.
VENDOR_LENGTH_BOUND = 0x2000


def looks_like_populated(probe: bytes) -> bool:
    """Cheap check on a short probe read: worth the full-length read?

    Only says no on the two junk shapes actually seen on real hardware
    (docs/69, live run 2026-08-18) plus bus-idle. Never says no just because
    the length field is *wrong* -- a short/corrupted-but-real primary (as
    section A was on this project's own unit) still has a small, plausible
    length field, and probing must never be the reason a real chip gets
    skipped. A wrong guess here is only allowed to cost time, never
    correctness.
    """
    if len(probe) < 4 or len(set(probe)) <= 1:      # bus idle
        return False
    length = int.from_bytes(probe[0:4], "little")
    return length <= VENDOR_LENGTH_BOUND


def write_backup(path: str, data: bytes) -> None:
    """Write `data` to `path`, timestamping any prior file out of the way
    first instead of overwriting it.

    This project's own rule for calibration data (CLAUDE.md: "Never
    overwrite calibration/* -- only timestamp") applies at least as strongly
    here: EEPROM 0x52 is the one thing on this scanner that cannot be
    re-derived, so a second run of this tool must never silently replace a
    previously-saved copy, verified or not, with whatever this run produced.
    """
    if os.path.exists(path):
        stamp = time.strftime("%Y%m%d-%H%M%S")
        prior = f"{path}.pre-{stamp}"
        os.rename(path, prior)
        print(f"     (kept prior file as {prior})")
    with open(path, "wb") as fh:
        fh.write(data)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.expanduser("~/pakon-eeprom-backup"))
    # 0xC00 covers the vendor's highest touched byte, 0xA24 (docs/69 §5.2).
    # Its own bound is 0x2000 (0x100160bc: cmp eax, 0x2000).
    ap.add_argument("--length", type=int, default=0xC00)
    ap.add_argument("--stage1", default=None)
    ap.add_argument("--no-load", action="store_true",
                    help="read from an ALREADY-LOADED scanner instead of "
                         "uploading stage 1. Verified on real hardware "
                         "2026-08-18: stage 1 answers 0xA9 but does NOT "
                         "honour the 0xA4 chip select, so every address "
                         "returns the boot personality "
                         "(c0 05 0f 35 f2 07 aa 04). #50's successful read "
                         "used the vendor application firmware (Pakon7.hex) "
                         "-- load it with pakon_load.py, then use this.")
    ap.add_argument("--force", action="store_true",
                    help="write a dump that FAILS validation, named .SUSPECT. "
                         "It is diagnostic output, not a backup.")
    ap.add_argument("--full-scan", action="store_true",
                    help="read every address at the full --length immediately, "
                         "skipping the cheap single-chunk probe that normally "
                         "decides whether an address is worth the full read. "
                         "Only 0x52 and 0x51 are documented as populated; the "
                         "other six read a recognisable junk pattern on real "
                         "hardware (docs/69, live run 2026-08-18), so the "
                         "probe skips those without reading them in full "
                         "twice each. Use this if that heuristic is ever in "
                         "doubt -- it costs time, never correctness either way.")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    stage1_path = args.stage1 or os.path.join(here, os.pardir, "vendor",
                                              "stage1_vendor.hex")
    if not os.path.exists(stage1_path):
        sys.exit(f"stage-1 loader not found at {stage1_path}")

    if args.no_load:
        from pakon_load import find_loaded
        dev = find_loaded()
        if dev is None:
            sys.exit("no LOADED scanner found -- run pakon_load.py first, or "
                     "drop --no-load to upload stage 1 here")
        print(f"device {dev.idVendor:04x}:{dev.idProduct:04x} "
              f"(already loaded; firmware untouched)")
        return _read_all(dev, args)

    dev = find_unloaded()
    if dev is None:
        # 04b4:8613 is the bare-FX2 ID for a unit with NO EEPROM personality.
        # A repaired unit boots its own C0 personality and shows 0f05:f235
        # rev aa07 while COLD -- find_unloaded() accepts that; only this
        # message used to suggest otherwise.
        sys.exit("no unloaded scanner found (expect 04b4:8613, or "
                 "0f05:f235 rev aa07 on a unit with a repaired boot EEPROM) "
                 "-- power-cycle it and do NOT load firmware first")

    print(f"device {dev.idVendor:04x}:{dev.idProduct:04x}")
    fx2 = Fx2(dev)
    print("uploading stage-1 loader (RAM only, no EEPROM write)")
    fx2.reset_8051(True)
    fx2.download(HexImage.load(stage1_path), False)
    fx2.reset_8051(False)
    time.sleep(0.4)
    return _read_all(dev, args)


def _read_all(dev, args) -> int:
    """Read every address, validate, save only what verifies."""
    os.makedirs(args.out, exist_ok=True)
    digests, results = {}, {}
    skipped = []
    print(f"\nreading with the vendor's parameters (wIndex {WINDEX:#06x}):")
    for n in range(8):
        i2c7 = n | 0x50

        if not args.full_scan:
            probe = read_one(dev, n, CHUNK)
            if isinstance(probe, bytes) and not looks_like_populated(probe):
                print(f"  n={n} I2C {i2c7:#04x}: probe ({len(probe)}B) "
                      f"doesn't look populated, skipping the full "
                      f"{args.length}B read -- {probe[:8].hex(' ')} "
                      f"(--full-scan to force it anyway)")
                skipped.append(n)
                continue

        first = read_one(dev, n, args.length)
        if isinstance(first, str):
            print(f"  n={n} I2C {i2c7:#04x}: {first}")
            continue
        if isinstance(first, PartialRead):
            print(f"  n={n} I2C {i2c7:#04x}: USB ERROR after {len(first)}/"
                  f"{args.length} bytes -- {first.error}")
            print("      keeping the partial data; validation below decides "
                  "whether it's enough of a backup, not this byte count.")
        time.sleep(0.05)
        second = read_one(dev, n, args.length)
        stable = (isinstance(second, bytes)
                  and not isinstance(first, PartialRead)
                  and not isinstance(second, PartialRead)
                  and second == first)
        md5 = hashlib.md5(first).hexdigest()
        digests.setdefault(md5, []).append(n)
        results[n] = first
        print(f"  n={n} I2C {i2c7:#04x}: {len(first)}B  "
              f"{'stable' if stable else 'UNSTABLE'}  md5 {md5[:12]}  "
              f"distinct {len(set(first))}")
        print(f"      {first[:16].hex(' ')}")

    if skipped:
        print(f"\n  {len(skipped)} address(es) skipped after a probe read: "
              f"{skipped} (--full-scan to read them in full anyway).")

    if not results:
        if skipped:
            print("\n  every address's probe looked unpopulated -- nothing "
                  "was worth a full read. --full-scan to double-check.")
        else:
            print("\n  nothing read.")
        return 1

    # If every address reads back the same bytes, the read is not addressing
    # individual devices -- CRC-valid or not, a file saved under this
    # condition would mislabel one real device's content as another's, so
    # every file gets forced to .SUSPECT regardless of its own CRC result.
    not_addressing = len(digests) == 1 and len(results) > 1
    if not_addressing:
        print("\n  WARNING: every address returned identical bytes.")
        print("  That means the read is not addressing individual devices;")
        print("  every file below is forced to .SUSPECT -- do NOT treat")
        print("  these as a backup, no matter what the CRC check below says.")
    else:
        print(f"\n  {len(digests)} distinct content(s) across {len(results)} "
              f"address(es) -- addressing is working.")

    # --- validate before calling anything a backup (issue #50) ------------
    print("\nvalidating against the vendor's own section headers and CRC-32:")
    saved = kept_suspect = 0
    for n, data in results.items():
        good = check.report(data, f"  n={n} I2C 0x{n | 0x50:02x}")
        keep_as_backup = good and not not_addressing
        if not keep_as_backup and not args.force:
            print("     NOT SAVED -- re-run with --force to keep it for "
                  "diagnosis.")
            continue
        suffix = "" if keep_as_backup else ".SUSPECT"
        path = os.path.join(args.out,
                            f"eeprom_n{n}_i2c{(n | 0x50):02x}.bin{suffix}")
        write_backup(path, data)
        print(f"     saved {path}")
        saved += keep_as_backup
        kept_suspect += not keep_as_backup

    print("\n  Nothing was written to the scanner.")
    if not saved:
        print("  NO VALID BACKUP WAS PRODUCED."
              + (f" ({kept_suspect} suspect file(s) kept.)" if kept_suspect
                 else ""))
        return 1
    print(f"  {saved} verified backup(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
