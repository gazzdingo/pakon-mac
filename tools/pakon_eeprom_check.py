#!/usr/bin/env python3
"""Decide whether an EEPROM 0x52 read is real, before anyone calls it a backup.

WHY
---
Issue #50: ``eeprom_backup.py`` read bus-idle ``0xFF`` for 8192 of 8192 bytes,
reported success, and wrote files. A backup of the one thing on this scanner
that cannot be re-derived must fail *loudly* when the read did not address
anything, not produce a plausible file. So nothing here trusts a byte count --
it checks the vendor's own section headers and CRCs.

THE LAYOUT (``docs/69`` §5.2/§5.3, from ``TLB.dll`` ``fcn.100163c0`` and the
CRC builder ``fcn.10015d30``)
-------------------------------------------------------------------------
Two sections, each stored twice::

    section A   398 bytes  primary 0x000   backup 0x400
    section B    36 bytes  primary 0x800   backup 0xA00

Each begins with ``{u32 length; u32 crc32;}`` and **the CRC covers the payload
only** -- ``[offset+8 … offset+length-1]``, excluding the header. The CRC is
built at runtime from the forward polynomial ``0x04C11DB7``, init
``0xFFFFFFFF``, final NOT: the standard reflected zlib/PKZIP CRC-32, so
``zlib.crc32`` is bit-identical and no table is reimplemented here.

THE OFF-BY-ONE
--------------
``backups/eeprom-i2c/eeprom_52.bin`` is shifted: ``file[k] = EEPROM[k+1]``
(``docs/69`` §5.5, four independent anchors). Its first bytes are ``01 00 00``
-- section A's length missing its leading ``0x8E``. That is a property of the
old ``fx2/eeprom_dump_bus.c`` dumper's extra priming read, not of the chip, so
:func:`verify` reports a suspected shift rather than silently correcting it.
Guessing a shift is how a bad read gets promoted to a good one.
"""
from __future__ import annotations

import zlib

# (name, offset, expected length) -- docs/69 §5.2
SECTIONS = (
    ("A", 0x000, 398),
    ("A-backup", 0x400, 398),
    ("B", 0x800, 36),
    ("B-backup", 0xA00, 36),
)

HIGHEST_BYTE = 0xA00 + 36        # 0xA24 = 2596


class SectionResult:
    __slots__ = ("name", "offset", "present", "length", "crc_stored",
                 "crc_actual", "ok", "note")

    def __init__(self, name, offset):
        self.name, self.offset = name, offset
        self.present = False
        self.length = self.crc_stored = self.crc_actual = None
        self.ok = False
        self.note = "not covered by this read"

    def __str__(self) -> str:
        if not self.present:
            return f"  {self.name:<9} @0x{self.offset:03X}  {self.note}"
        return (f"  {self.name:<9} @0x{self.offset:03X}  len={self.length} "
                f"crc={self.crc_stored:#010x} "
                f"{'OK' if self.ok else 'BAD -- ' + self.note}")


def check_section(data: bytes, name: str, offset: int, expect_len: int
                  ) -> SectionResult:
    r = SectionResult(name, offset)
    if len(data) < offset + 8:
        return r
    r.present = True
    r.length = int.from_bytes(data[offset:offset + 4], "little")
    r.crc_stored = int.from_bytes(data[offset + 4:offset + 8], "little")

    if r.length != expect_len:
        r.note = f"length {r.length} != expected {expect_len}"
        return r
    end = offset + r.length
    if len(data) < end:
        r.note = f"truncated: need {end} bytes, have {len(data)}"
        return r
    r.crc_actual = zlib.crc32(data[offset + 8:end]) & 0xFFFFFFFF
    if r.crc_actual != r.crc_stored:
        r.note = f"CRC {r.crc_actual:#010x} != stored {r.crc_stored:#010x}"
        return r
    r.ok = True
    r.note = "ok"
    return r


def looks_like_bus_idle(data: bytes) -> bool:
    """All ``0xFF`` (or all one byte) -- nothing was being addressed."""
    return len(set(data)) <= 1


def suspected_off_by_one(data: bytes) -> bool:
    """``file[k] == EEPROM[k+1]``: section A's length with its top byte eaten.

    ``0x0000018E`` little-endian is ``8e 01 00 00``; losing the first byte
    leaves the read starting ``01 00 00``. See ``docs/69`` §5.5.
    """
    return len(data) >= 3 and data[0:3] == b"\x01\x00\x00"


def verify(data: bytes) -> tuple[bool, list[SectionResult], list[str]]:
    """``(good, per-section results, warnings)``.

    ``good`` requires at least one section to pass CRC. The vendor itself
    falls back to the backup copy, so one good copy is a real backup and
    demanding all four would reject dumps the scanner considers healthy.
    """
    warnings: list[str] = []
    if looks_like_bus_idle(data):
        b = data[0] if data else None
        warnings.append(
            f"every byte is {b:#04x} -- this is a bus-idle read, not an "
            f"EEPROM. Nothing was being addressed." if b is not None
            else "empty read")
        return False, [], warnings

    results = [check_section(data, n, o, ln) for n, o, ln in SECTIONS]
    good = [r for r in results if r.ok]

    if not good and suspected_off_by_one(data):
        warnings.append(
            "no section verified, and the read starts 01 00 00 -- the "
            "signature of the docs/69 §5.5 off-by-one (file[k] = EEPROM[k+1]). "
            "Not corrected here: shifting a failed read until it validates is "
            "how a bad dump gets mistaken for a good one.")
    if len(data) < HIGHEST_BYTE:
        warnings.append(
            f"read is {len(data)} bytes; the vendor touches up to "
            f"{HIGHEST_BYTE} (0x{HIGHEST_BYTE:X}), so later sections were "
            f"not covered.")
    return bool(good), results, warnings


def report(data: bytes, label: str = "dump") -> bool:
    """Print a verdict. Returns True if the dump is worth keeping."""
    good, results, warnings = verify(data)
    print(f"{label}: {len(data)} bytes, {len(set(data))} distinct values")
    for r in results:
        print(r)
    for w in warnings:
        print(f"  ! {w}")
    print(f"  => {'USABLE' if good else 'NOT A VALID BACKUP'}")
    return good


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        sys.exit(f"usage: {sys.argv[0]} <dump.bin> [...]")
    rc = 0
    for path in sys.argv[1:]:
        with open(path, "rb") as fh:
            if not report(fh.read(), path):
                rc = 1
        print()
    sys.exit(rc)
