#!/usr/bin/env python3
"""The corrected read path and its validation, exercised without a scanner.

Issue #50 was not caught by a test because there was no way to run the read
path offline: it needed a device. So this stands a fake one up. The fake is
deliberately strict -- it models the thing that actually went wrong, a chip
that answers only when it has been selected, and returns bus idle when it has
not. Under the OLD code (no 0xA4 select) it returns 0xFF, which is exactly
what the real F-135+ did.
"""
from __future__ import annotations

import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["PAKON_USB_GUARD_QUIET"] = "1"

import pakon_eeprom_check as check          # noqa: E402
import pakon_usb_guard as guard             # noqa: E402
import eeprom_backup as B                   # noqa: E402

PASS = FAIL = 0


def ok(cond, what):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok    {what}")
    else:
        FAIL += 1
        print(f"  FAIL  {what}")


def build_image() -> bytes:
    """A synthetic 0x52 with the vendor's layout and real CRC-32s."""
    img = bytearray(b"\x00" * check.HIGHEST_BYTE)
    for name, off, length in check.SECTIONS:
        payload = bytes((off // 4 + i) & 0xFF for i in range(length - 8))
        img[off:off + 4] = length.to_bytes(4, "little")
        img[off + 4:off + 8] = (zlib.crc32(payload) & 0xFFFFFFFF
                                ).to_bytes(4, "little")
        img[off + 8:off + length] = payload
    return bytes(img)


IMAGE = build_image()


class FakeDev:
    """Answers 0xA9 only while a chip is selected -- otherwise bus idle."""

    def __init__(self, image, honour_select=True):
        self.image, self.honour_select = image, honour_select
        self.selected = None
        self.selects = 0
        self.chunk_sizes = []

    def ctrl_transfer(self, bmrt, req, wval, widx, data_or_len, timeout=None):
        if req == B.SELECT:
            assert widx == 0x1234, "select must carry the magic wIndex"
            assert wval & 1, "this tool must only ever select for reading"
            self.selected = (wval >> 1) & 0x7F
            self.selects += 1
            return 0
        if req == B.READ:
            n = data_or_len
            self.chunk_sizes.append(n)
            if self.honour_select and self.selected != 0x52:
                return bytearray(b"\xff" * n)      # bus idle, as on real HW
            return bytearray(self.image[wval:wval + n])
        raise AssertionError(f"unexpected bRequest {req:#04x}")


print("the corrected sequence reads the chip")
guard._selected_device = None
dev = FakeDev(IMAGE)
data = B.read_one(dev, 2, len(IMAGE))
ok(isinstance(data, bytes) and data == IMAGE,
   "read_one reconstructs the image exactly")
ok(dev.selects == (len(IMAGE) + B.CHUNK - 1) // B.CHUNK,
   f"the select is re-issued before every chunk ({dev.selects} selects)")
ok(max(dev.chunk_sizes) <= 32, "no chunk exceeds the vendor's 32 bytes")

print("\nvalidation accepts it")
good, results, warnings = check.verify(data)
ok(good, "verify() passes a well-formed image")
ok(all(r.ok for r in results), "all four sections verify (CRC-32 over payload)")
ok(not warnings, f"no warnings ({warnings})")

print("\nthe issue #50 failure can no longer masquerade as a backup")
idle = b"\xff" * check.HIGHEST_BYTE
good_idle, _, warn_idle = check.verify(idle)
ok(not good_idle, "an all-0xFF read is rejected")
ok(any("bus-idle" in w for w in warn_idle), "and is named as a bus-idle read")

print("\nthe OLD behaviour (no select) is what the real scanner refused")
guard._selected_device = None
dev2 = FakeDev(IMAGE)
raw = bytes(dev2.ctrl_transfer(0xC0, B.READ, ((2 | 0x50) << 1) | 1, 0x1234,
                               256))
ok(set(raw) == {0xFF},
   "reading with the address in wValue and no select returns 0xFF")
ok(not check.verify(raw)[0], "and validation rejects it")

print("\ncorruption is caught, not waved through")
bad = bytearray(IMAGE)
bad[0x100] ^= 0xFF                      # one bit inside section A's payload
good_bad, res_bad, _ = check.verify(bytes(bad))
ok(good_bad, "a flipped byte in section A still leaves the backups verifying")
ok(not res_bad[0].ok, "but section A itself is reported CRC BAD")
allbad = bytearray(IMAGE)
for _, off, length in check.SECTIONS:
    allbad[off + 12] ^= 0xFF
ok(not check.verify(bytes(allbad))[0], "all four corrupted -> rejected")

print("\nthe off-by-one signature is flagged, never silently corrected")
shifted = IMAGE[1:]
ok(check.suspected_off_by_one(shifted),
   "a dump shifted by one is recognised (docs/69 sec5.5)")
ok(not check.verify(shifted)[0], "and is still rejected, not auto-repaired")

print("\na read that never reaches section B is not a valid backup")
# Section A is 0x000-0x18E, its backup 0x400-0x59E -- both well inside a
# truncated read that stops before section B (0x800). Before this fix,
# `good` only needed ONE of the four copies (of anything) to pass CRC, so a
# read that stopped here -- e.g. read_one() cut short by a real USB error, or
# --length passed too small -- was reported USABLE despite section B (a
# different, non-redundant payload, not a spare copy of A) never having been
# read at all.
truncated_before_b = IMAGE[:0x600]
good_trunc, results_trunc, warn_trunc = check.verify(truncated_before_b)
ok(not good_trunc,
   "a read covering only section A (+ its backup) is rejected")
ok(any(r.ok for r in results_trunc if r.name.startswith("A")),
   "section A itself still verifies fine -- it's B that's the problem")
ok(any("section(s) B" in w for w in warn_trunc),
   f"and the reason names section B specifically ({warn_trunc})")

print("\nread_one surfaces a mid-read USB error instead of masking it")
import usb.core                              # noqa: E402


class FlakyDev(FakeDev):
    """Like FakeDev, but the data phase throws after `fail_after` chunks."""

    def __init__(self, image, fail_after):
        super().__init__(image)
        self.fail_after = fail_after
        self.reads_done = 0

    def ctrl_transfer(self, bmrt, req, wval, widx, data_or_len, timeout=None):
        if req == B.READ:
            if self.reads_done >= self.fail_after:
                raise usb.core.USBError("simulated mid-read stall")
            self.reads_done += 1
        return super().ctrl_transfer(bmrt, req, wval, widx, data_or_len, timeout)


guard._selected_device = None
flaky = FlakyDev(IMAGE, fail_after=3)
partial = B.read_one(flaky, 2, len(IMAGE))
ok(isinstance(partial, B.PartialRead),
   "a mid-read USBError comes back as PartialRead, not plain bytes")
ok(bool(getattr(partial, "error", "")),
   f"and carries the error text ({getattr(partial, 'error', None)!r})")
ok(len(partial) == 3 * B.CHUNK,
   "and keeps exactly the bytes read before the error, not padded/discarded")

print("\nthe guard permits the whole sequence")
guard._selected_device = None
try:
    guard.check(0x40, B.SELECT, ((2 | 0x50) << 1) | 1, 0x1234, True)
    guard.check(0xC0, B.READ, 0x000, 0x1234, False)
    ok(True, "select + data phase both pass the allow-list")
except guard.TransferDenied as e:
    ok(False, f"denied: {e}")

print(f"\n{PASS}/{PASS + FAIL} checks passed")
sys.exit(0 if FAIL == 0 else 1)
