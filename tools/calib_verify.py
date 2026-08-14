#!/usr/bin/env python3
"""Judge whether an EEPROM read is REAL -- by structure, never by re-reading.

THE POINT OF THIS FILE
----------------------
The obvious way to check a read is to do it again and compare. On this
hardware that is the one thing you must never do. From
backups/eeprom-i2c/README.md, established on real hardware 2026-08-05:

    These EEPROMs return good data on the FIRST transaction after a power
    cycle and degrade on every read after it. The second read of a power
    cycle already differed in 180 of 256 bytes; by the third, both devices
    read entirely 0xFF. Status stays "ok" throughout.

    A repeated-read hash comparison is therefore WORSE than useless: it
    converges on stable garbage. A 7-pass run reported "STABLE -- backup is
    trustworthy" for 256 bytes of 0xFF.

So every check in this module looks at ONE buffer that is already in memory or
already on disk. Nothing here touches USB, and nothing here can cause a read.
That is a deliberate structural property of the module: it imports no usb
package and takes bytes, not devices.

WHAT "REAL" LOOKS LIKE -- derived, not guessed
----------------------------------------------
Verified by arithmetic against backups/eeprom-i2c/eeprom_52.bin, which is
itself two byte-identical first-reads from separate power cycles:

  0x0F        u32 LE  scanner serial number (16275 on the owner's unit)
  0x25..0x9C  the 3x10 colour-negative matrix, float32 LE, row-major,
              row stride 40 bytes. All 30 values equal the Windows registry's
              HKLM\\SOFTWARE\\Pakon\\TLB\\ColorKodak\\NegMatrix0..29 exactly.
  0x9D..      the 3x10 colour-reversal matrix in the same layout, whose
              diagonal is 0.25 -- landing at 0x9D, 0xC9, 0xF5, a 44-byte
              stride because the diagonal of a 3x10 steps 40+4 bytes.
              It is TRUNCATED by the 256-byte page boundary.

docs/35 had already spotted the three large values at 0x49/0x71/0x99 with a
40-byte spacing, and the three 0.25s at 0x9D/0xC9/0xF5 with a 44-byte spacing,
but left the record boundary open because two spacings coexisted. They are one
structure: 0x49/0x71/0x99 is element 9 of each negative-matrix row, and the
44-byte spacing is a matrix diagonal. See docs/60.

GENERAL vs THIS-UNIT
--------------------
Another owner's scanner has DIFFERENT numbers in these fields -- that is the
whole point of per-unit calibration. So the general checks are structural:

  * the colour-reversal diagonal is 0.25, which is a plain 14-bit -> 12-bit
    shift (docs/58 s4.4) and therefore expected to be the same on every unit;
  * the negative matrix diagonal is a set of three near-equal scale factors
    around 0.28, mapping 14-bit onto the 12-bit clamp;
  * the three pedestals are positive, finite, ascending R < G < B;
  * float32 LE at alignment 1 beats every other alignment on a
    plausible-value census.

The owner's exact values are checked too, but only ever REPORTED, never
required -- a scanner that fails them is a different scanner, not a bad read.

CRC -- identified, not yet checkable
------------------------------------
docs/35 recorded that two CRC32-checked sections of 398 and 36 bytes exist, and
guessed that 398 bytes must span "devices we have never read". docs/69 s5.2
settles it from the disassembly and the guess was wrong: there is ONE device,
at 0x52, addressed with a flat 16-bit byte offset, and the sections live at
EEPROM offsets 0x000 (398 B, backup at 0x400) and 0x800 (36 B, backup at 0xA00).
The CRC itself is now fully identified -- see crc_status().

It still cannot be evaluated here, for two reasons that are now exact rather
than vague: this image holds 255 of section A's 390 payload bytes, and it is
off by one against the EEPROM's own addressing (docs/69 s5.5). That is why the
earlier 7-variant search -- zlib/ISO-HDLC, BZIP2, MPEG-2, POSIX, JAMCRC,
CRC-32C, XFER, every start offset 0..63, every length to 140, the stored word
allowed anywhere as LE or BE -- found ZERO validating pairs. It was looking for
a checksum over data that was neither complete nor aligned.

crc_status() reports that state rather than inventing a verdict. The read in
docs/69 s5.6 would make it checkable, and a validating CRC is worth more than
every structural check in this file put together.

A WARNING ABOUT THE OFFSETS BELOW
---------------------------------
SERIAL_OFF, NEG_MATRIX_OFF and POS_MATRIX_OFF are offsets into the IMAGE this
project's firmware produces, and that image starts at EEPROM byte 1: the dump
routine's priming read consumes byte 0 (docs/69 s5.5, proven against the
registry hive on nine independent values). They are correct as written and
every one of them becomes wrong by one if that firmware is ever fixed. Do not
"correct" them on paper -- they must change only together with the firmware and
a version marker on the stored image, or the only good read that exists stops
decoding.
"""
from __future__ import annotations

import argparse
import math
import struct
import sys
from pathlib import Path

PAGE = 256

# ---- layout, verified against backups/eeprom-i2c/eeprom_52.bin -------------
SERIAL_OFF = 0x0F           # u32 LE
NEG_MATRIX_OFF = 0x25       # 3 rows x 10 float32 LE
POS_MATRIX_OFF = 0x9D       # same layout, truncated by the page boundary
ROW_STRIDE = 40             # 10 * 4
ROWS, COLS = 3, 10

# element 9 of each negative row -- the per-channel pedestal
PEDESTAL_OFFSETS = tuple(NEG_MATRIX_OFF + r * ROW_STRIDE + 9 * 4 for r in range(ROWS))
# diagonal of the reversal matrix -- steps 44 bytes (40 for the row, 4 for the column)
POS_DIAG_OFFSETS = tuple(POS_MATRIX_OFF + r * (ROW_STRIDE + 4) for r in range(ROWS))

# The owner's unit. Reported for recognition; never required.
OWNER_SERIAL = 16275
OWNER_PEDESTALS = (159.593735, 444.749695, 635.535217)

# The firmware pre-fills its buffers with this. Neither 0x00 nor 0xFF, so
# "the firmware never ran" stays distinguishable from "the part answered
# 0xFF" -- which matters enormously, because all-0xFF is what a degraded read
# looks like.
NOT_READ_SENTINEL = 0xEE

# States, worst to best.
NOT_READ = "not-read"
ERASED = "erased"
BLANK = "blank"
DEGRADED = "degraded"
UNSTRUCTURED = "unstructured"
GOOD = "good"

_ORDER = {NOT_READ: 0, ERASED: 1, BLANK: 2, DEGRADED: 3, UNSTRUCTURED: 4, GOOD: 5}

KIND_CALIBRATION = "calibration"
KIND_FX2_BOOT = "fx2-boot"
KIND_UNKNOWN = "unknown"


def is_usable(state: str) -> bool:
    """Would we be willing to render a photograph with this?"""
    return _ORDER.get(state, 0) >= _ORDER[UNSTRUCTURED]


def better(a: str, b: str) -> bool:
    return _ORDER.get(a, 0) > _ORDER.get(b, 0)


# --------------------------------------------------------------------------
# primitives
# --------------------------------------------------------------------------

def entropy(data: bytes) -> float:
    """Shannon entropy in bits/byte. All-0xFF is 0.0; real calibration ~5-6."""
    if not data:
        return 0.0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in counts if c) + 0.0


def _plausible(v: float) -> bool:
    """A float that could be a real engineering quantity."""
    if v != v or v in (float("inf"), float("-inf")):
        return False
    return v == 0.0 or 1e-8 < abs(v) < 1e8


def float_census(data: bytes) -> dict:
    """How float-like is this buffer, at each alignment and endianness?

    Real calibration is dense float32 LE at alignment 1. Junk is not.
    """
    out = {}
    for endian, fmt in (("LE", "<f"), ("BE", ">f")):
        for align in range(4):
            ok = total = 0
            for off in range(align, len(data) - 3, 4):
                total += 1
                if _plausible(struct.unpack_from(fmt, data, off)[0]):
                    ok += 1
            out[f"{endian}{align}"] = (ok, total)
    best = max(out, key=lambda k: (out[k][0] / out[k][1]) if out[k][1] else 0)
    return {"census": out, "best": best,
            "best_ratio": out[best][0] / out[best][1] if out[best][1] else 0.0}


def read_matrix(data: bytes, base: int) -> list[list[float | None]]:
    """Decode a 3x10 float32 LE matrix; None where the page runs out."""
    rows = []
    for r in range(ROWS):
        row = []
        for c in range(COLS):
            off = base + r * ROW_STRIDE + c * 4
            row.append(struct.unpack_from("<f", data, off)[0]
                       if off + 4 <= len(data) else None)
        rows.append(row)
    return rows


def crc_status(_data: bytes) -> dict:
    """Deliberately not a verdict -- but no longer a mystery. See docs/69 s5.3.

    The CRC is now fully identified: standard reflected zlib/PKZIP CRC-32
    (init 0xFFFFFFFF, final NOT), built at runtime in TLB.dll's fcn.10015d30
    from the forward polynomial 0x04C11DB7. Each section is
    {u32 length; u32 crc32; payload}, and the CRC covers the PAYLOAD ONLY --
    bytes [offset+8 .. offset+length-1], header excluded.

    Section A is 398 bytes at EEPROM offset 0x000 (backup at 0x400), so its CRC
    covers 0x008..0x18D. It still cannot be checked here, for two reasons that
    are now precise rather than vague:

      1. this image holds 255 of those 390 payload bytes; and
      2. this image is OFF BY ONE -- eeprom_52.bin[k] == EEPROM[k+1] -- so even
         the bytes we have are misaligned against the CRC's own addressing.

    That is why the earlier 7-variant, all-offsets search found nothing: it was
    searching for a CRC over data that is neither complete nor aligned.

    Once the read described in docs/69 s5.6 exists this becomes checkable, and
    it is worth far more than the six structural checks -- a validating CRC is
    the vendor's own verdict on its own data, and it costs no extra read.
    """
    return {
        "checked": False,
        "reason": "zlib CRC-32 over EEPROM 0x008..0x18D (section A payload), "
                  "stored at 0x004. This image holds 255 of those 390 bytes "
                  "and is offset by one (file[k] = EEPROM[k+1]), so the CRC "
                  "cannot be evaluated. See docs/69 s5.3 and s5.5.",
    }


# --------------------------------------------------------------------------
# verification
# --------------------------------------------------------------------------

def _check(checks: list, name: str, ok: bool | None, detail: str) -> None:
    checks.append({"name": name, "ok": ok, "detail": detail})


def verify_fx2_boot(data: bytes) -> dict:
    """The FX2 boot personality at 0x51: C0/C2 signature + VID/PID/DID.

    docs/13 and backups/eeprom-i2c/README.md: the correct contents for an
    F-135 are c0 05 0f 35 f2 07 aa 04. On the owner's unit this device is
    ERASED, which is why the scanner enumerates as 04b4:8613 and needs the
    host to load firmware. An intact one on someone else's machine is
    genuinely valuable and must be captured before anything else happens.
    """
    checks: list = []
    sig = data[0] if data else None
    ok_sig = sig in (0xC0, 0xC2)
    _check(checks, "c0/c2 signature", ok_sig,
           f"byte 0 = {sig:#04x}" if sig is not None else "empty")
    info = {}
    if ok_sig and len(data) >= 8:
        vid, pid, did = struct.unpack_from("<HHH", data, 1)
        info = {"vid": vid, "pid": pid, "did": did, "cfg": data[7],
                "format": "C0" if sig == 0xC0 else "C2"}
        known = (vid, pid) in ((0x0F05, 0xF235), (0x0F05, 0x35F2),
                               (0x0F05, 0xF135), (0x0F05, 0xF335))
        _check(checks, "vid/pid is a Pakon scanner", known,
               f"{vid:04x}:{pid:04x} did={did:04x}")
    return {"checks": checks, "info": info, "signature_ok": ok_sig}


def verify_calibration(data: bytes) -> dict:
    """Structural checks for the calibration page (0x52 on the owner's unit)."""
    checks: list = []
    info: dict = {}

    neg = read_matrix(data, NEG_MATRIX_OFF)
    pos = read_matrix(data, POS_MATRIX_OFF)
    info["neg_matrix"] = neg
    info["pos_matrix"] = pos

    # 1. every negative-matrix value finite and plausible -- 30 of 30
    flat = [v for row in neg for v in row if v is not None]
    n_ok = sum(1 for v in flat if _plausible(v))
    _check(checks, "negative matrix parses", flat and n_ok == len(flat),
           f"{n_ok}/{len(flat)} plausible float32 LE")

    # 2. diagonal = three near-equal scale factors mapping 14-bit -> 12-bit
    diag = [neg[i][i] for i in range(ROWS) if neg[i][i] is not None]
    diag_ok = (len(diag) == ROWS and all(0.05 < v < 1.0 for v in diag)
               and (max(diag) - min(diag)) < 0.25 * max(diag))
    _check(checks, "negative diagonal is a scale triple", diag_ok,
           "  ".join(f"{v:.6f}" for v in diag) if diag else "unreadable")

    # 3. pedestals: positive, finite, ascending R < G < B
    ped = [neg[r][9] for r in range(ROWS) if neg[r][9] is not None]
    ped_ok = (len(ped) == ROWS and all(0.0 < v < 20000.0 for v in ped)
              and ped[0] < ped[1] < ped[2])
    _check(checks, "pedestals positive and ascending", ped_ok,
           "  ".join(f"{v:.3f}" for v in ped) if ped else "unreadable")
    info["pedestals"] = ped

    # 4. reversal diagonal == 0.25 exactly. Expected on EVERY unit: docs/58
    #    s4.4 reads it as a plain 14-bit -> 12-bit shift, not a fitted value.
    pdiag = [pos[i][i] for i in range(ROWS) if pos[i][i] is not None]
    pd_ok = bool(pdiag) and all(v == 0.25 for v in pdiag)
    _check(checks, "reversal diagonal is 0.25", pd_ok,
           ("  ".join(f"{v:.6f}" for v in pdiag) +
            (f"  ({len(pdiag)}/3 within the page)" if len(pdiag) < ROWS else ""))
           if pdiag else "unreadable")
    info["pos_diagonal"] = pdiag

    # 5. float32 LE at alignment 1 should win the census
    cen = float_census(data)
    info["float_census"] = cen
    _check(checks, "float32 LE alignment 1 dominates", cen["best"] == "LE1",
           f"best {cen['best']} at {cen['best_ratio']:.0%}")

    # 6. serial number
    serial = None
    if len(data) >= SERIAL_OFF + 4:
        serial = struct.unpack_from("<I", data, SERIAL_OFF)[0]
    info["serial"] = serial
    _check(checks, "serial number plausible",
           serial is not None and 1 <= serial <= 999_999,
           f"{serial} at {SERIAL_OFF:#04x}" if serial is not None else "short")

    # Recognition only -- never a requirement.
    info["matches_owner_unit"] = bool(
        serial == OWNER_SERIAL and len(ped) == ROWS
        and all(abs(a - b) < 1e-3 for a, b in zip(ped, OWNER_PEDESTALS)))

    strong = sum(1 for c in checks if c["ok"])
    return {"checks": checks, "info": info, "passed": strong,
            "total": len(checks)}


def verify(data: bytes, addr7: int | None = None) -> dict:
    """Judge one device image. Pure function of bytes -- causes no I/O."""
    n = len(data)
    ff = data.count(0xFF)
    zero = data.count(0x00)
    ee = data.count(NOT_READ_SENTINEL)
    distinct = len(set(data))
    stats = {"bytes": n, "ff": ff, "zero": zero, "distinct": distinct,
             "entropy": round(entropy(data), 3),
             "ff_fraction": round(ff / n, 4) if n else 0.0}

    result = {"addr7": addr7, "stats": stats, "checks": [], "info": {},
              "crc": crc_status(data), "kind": KIND_UNKNOWN}

    if n == 0:
        result.update(state=NOT_READ, summary="empty buffer")
        return result
    if ee == n:
        result.update(state=NOT_READ,
                      summary="all 0xEE -- the firmware never read this "
                              "device, so this is not data at all")
        return result
    if ff == n:
        result.update(state=ERASED,
                      summary="all 0xFF -- erased, absent, or a DEGRADED "
                              "read. Never overwrite a good backup with this.")
        return result
    if zero == n:
        result.update(state=BLANK, summary="all 0x00 -- blank or a failed read")
        return result

    # Which device is this trying to be?
    boot = verify_fx2_boot(data)
    if boot["signature_ok"]:
        result["kind"] = KIND_FX2_BOOT
        result["checks"] = boot["checks"]
        result["info"] = boot["info"]
        ok = all(c["ok"] for c in boot["checks"] if c["ok"] is not None)
        result["state"] = GOOD if ok else UNSTRUCTURED
        result["summary"] = ("FX2 boot personality, "
                             + ("intact" if ok else "signature present but "
                                                   "contents unrecognised"))
        return result

    cal = verify_calibration(data)
    result["checks"] = cal["checks"]
    result["info"] = cal["info"]
    # The two checks that generalise across units carry the verdict.
    load_bearing = [c for c in cal["checks"]
                    if c["name"] in ("negative matrix parses",
                                     "negative diagonal is a scale triple",
                                     "pedestals positive and ascending",
                                     "reversal diagonal is 0.25")]
    strong = sum(1 for c in load_bearing if c["ok"])
    if strong == len(load_bearing):
        result["kind"] = KIND_CALIBRATION
        result["state"] = GOOD
        who = (" -- this is the owner's unit, serial "
               f"{cal['info'].get('serial')}") if cal["info"].get(
                   "matches_owner_unit") else ""
        result["summary"] = ("parses as the vendor calibration layout"
                             f" ({cal['passed']}/{cal['total']} checks){who}")
    elif strong > 0:
        result["kind"] = KIND_CALIBRATION
        result["state"] = DEGRADED
        result["summary"] = (f"only {strong}/{len(load_bearing)} structural "
                             "checks pass -- a partial or degraded read")
    elif stats["ff_fraction"] > 0.5 or stats["entropy"] < 2.0:
        result["state"] = DEGRADED
        result["summary"] = (
            f"{stats['ff_fraction']:.0%} of bytes are 0xFF, entropy "
            f"{stats['entropy']} bits/byte -- erased, absent, or a degraded "
            "read. A single read cannot tell those apart, and re-reading to "
            "find out would destroy the answer.")
    else:
        result["state"] = UNSTRUCTURED
        result["summary"] = ("data present but it does not match any layout "
                             "we know -- keep it, judge it by hand")
    return result


def cross_page_checks(devices: dict[int, bytes]) -> list[dict]:
    """Checks that need more than one device. Still no re-reading.

    Requested by the colour task in docs/59: the colour-reversal matrix starts
    at 0x9D of the calibration page and needs 120 bytes, so elements 24..29
    fall off the end of the 256-byte page and are currently zero-filled on an
    assumption.

    THE PREMISE OF THIS CHECK HAS BEEN REFUTED -- see docs/69 s5.2
    ---------------------------------------------------------------
    It was written on the belief that 0x52 is one page of a multi-page device
    and that a 24C04/24C08 would expose the continuation as 0x53. It does not.
    TLB.dll addresses the calibration part with a FLAT 16-BIT BYTE OFFSET in
    wValue (fcn.100160a0 at 0x100161a7), bounded at 0x2000, and reaches offset
    0xA24 -- above the 2048 bytes any device-select scheme can cover. There is
    exactly one device, at 0x52, with a 2-byte word address, and the vendor
    never addresses any other index (all four call sites push 2).

    So the missing six values are at EEPROM 0x0FE..0x115, immediately past this
    256-byte window and BEHIND THE SAME ADDRESS. A device at 0x53 answering at
    all would mean something unexpected about that unit's hardware, not the
    continuation of this matrix.

    The check is kept because it is free, because it is still a true statement
    about any device that does answer at 0x53, and because on another owner's
    scanner a populated 0x53 is worth surfacing. But a null result here is
    EXPECTED and is not evidence that anything is missing -- the honest remedy
    is the full-length read described in docs/69 s5.6.

    Costs nothing: it reads two buffers that are already in hand.
    """
    checks: list = []
    cal_addr = next((a for a, d in sorted(devices.items())
                     if verify(d, a)["kind"] == KIND_CALIBRATION), None)
    if cal_addr is None:
        return checks

    nxt = devices.get(cal_addr + 1)
    if nxt is None:
        _check(checks, "reversal matrix continuation", None,
               f"device 0x{cal_addr + 1:02x} did not answer, so the last six "
               f"values of the reversal matrix remain unconfirmed "
               f"(zero-filled by assumption)")
        return checks

    vals = [struct.unpack_from("<f", nxt, i * 4)[0] for i in range(6)]
    all_zero = all(v == 0.0 for v in vals)
    _check(checks, "reversal matrix continuation", all_zero,
           ("six zeros on 0x%02x -- consistent with the zero-fill, though "
            "docs/69 s5.2 shows the real continuation is at EEPROM 0x0FE "
            "behind 0x52, not here" % (cal_addr + 1)) if all_zero else
           ("got " + " ".join(f"{v:g}" for v in vals) + " on 0x%02x -- this "
            "device holds something of its own. The reversal continuation is "
            "NOT here (docs/69 s5.2); whatever this is, keep it and look at "
            "it by hand." % (cal_addr + 1)))
    return checks


def describe(result: dict) -> str:
    """One-screen human summary. Used by the CLI and the app."""
    s = result["stats"]
    head = (f"  state    {result['state'].upper()}  ({result['kind']})\n"
            f"  {result['summary']}\n"
            f"  bytes {s['bytes']}  0xFF {s['ff']}  0x00 {s['zero']}  "
            f"distinct {s['distinct']}  entropy {s['entropy']} bits/byte")
    lines = [head]
    for c in result["checks"]:
        mark = "ok  " if c["ok"] else ("--  " if c["ok"] is None else "FAIL")
        lines.append(f"    [{mark}] {c['name']}: {c['detail']}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Verify an EEPROM image by structure. Reads files only; "
                    "never touches the scanner.")
    ap.add_argument("files", nargs="+", type=Path)
    args = ap.parse_args()
    worst = GOOD
    for f in args.files:
        data = f.read_bytes()
        r = verify(data)
        print(f"\n{f}")
        print(describe(r))
        if better(worst, r["state"]):
            worst = r["state"]
    print()
    return 0 if is_usable(worst) else 1


if __name__ == "__main__":
    sys.exit(main())
