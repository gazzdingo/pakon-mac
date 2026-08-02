#!/usr/bin/env python3
"""Intel HEX parsing and inspection for Pakon EZ-USB firmware images.

Also used as a library by pakon_fw.py.

  ./pakon_hex.py Pakon7.hex --segments --descriptors
"""
from __future__ import annotations

import argparse
import re
import sys

# EZ-USB FX2 (CY7C68013A) internal RAM is 16 KB at 0x0000-0x3FFF.
FX2_INTERNAL_RAM_END = 0x4000
FX2_CPUCS = 0xE600


class HexImage:
    """A parsed Intel HEX file."""

    def __init__(self, mem: dict[int, int], path: str = "<mem>"):
        self.mem = mem
        self.path = path

    @classmethod
    def load(cls, path: str) -> "HexImage":
        mem: dict[int, int] = {}
        base = 0
        with open(path) as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                if not line.startswith(":"):
                    raise ValueError(f"{path}:{lineno}: not an Intel HEX record")
                try:
                    raw = bytes.fromhex(line[1:])
                except ValueError as exc:
                    raise ValueError(f"{path}:{lineno}: bad hex: {exc}") from exc
                if len(raw) < 5:
                    raise ValueError(f"{path}:{lineno}: record too short")
                if (sum(raw) & 0xFF) != 0:
                    raise ValueError(f"{path}:{lineno}: checksum mismatch")

                count, addr, rectype = raw[0], (raw[1] << 8) | raw[2], raw[3]
                data = raw[4:4 + count]
                if len(data) != count:
                    raise ValueError(f"{path}:{lineno}: truncated record")

                if rectype == 0x00:          # data
                    for i, b in enumerate(data):
                        mem[base + addr + i] = b
                elif rectype == 0x01:        # EOF
                    break
                elif rectype == 0x02:        # extended segment address
                    base = ((data[0] << 8) | data[1]) << 4
                elif rectype == 0x04:        # extended linear address
                    base = ((data[0] << 8) | data[1]) << 16
                else:
                    raise ValueError(f"{path}:{lineno}: unsupported record type {rectype:#04x}")
        if not mem:
            raise ValueError(f"{path}: no data records")
        return cls(mem, path)

    def segments(self) -> list[tuple[int, bytes]]:
        """Contiguous (start_address, data) blocks, ascending."""
        addrs = sorted(self.mem)
        out: list[tuple[int, bytes]] = []
        start = prev = addrs[0]
        buf = [self.mem[start]]
        for a in addrs[1:]:
            if a == prev + 1:
                buf.append(self.mem[a])
            else:
                out.append((start, bytes(buf)))
                start, buf = a, [self.mem[a]]
            prev = a
        out.append((start, bytes(buf)))
        return out

    def chunked(self, max_len: int = 1024) -> list[tuple[int, bytes]]:
        """Segments split so no block exceeds max_len, and none straddles the
        FX2 internal/external RAM boundary (so each block has one request code)."""
        out: list[tuple[int, bytes]] = []
        for addr, data in self.segments():
            off = 0
            while off < len(data):
                a = addr + off
                take = min(max_len, len(data) - off)
                if a < FX2_INTERNAL_RAM_END < a + take:
                    take = FX2_INTERNAL_RAM_END - a
                out.append((a, data[off:off + take]))
                off += take
        return out

    def total_bytes(self) -> int:
        return len(self.mem)

    # ---- inspection -----------------------------------------------------

    def _flat(self) -> tuple[int, bytes]:
        lo, hi = min(self.mem), max(self.mem)
        return lo, bytes(self.mem.get(a, 0xFF) for a in range(lo, hi + 1))

    def device_descriptors(self) -> list[dict]:
        lo, blob = self._flat()
        found = []
        for m in re.finditer(rb"\x12\x01", blob):
            o = m.start()
            d = blob[o:o + 18]
            if len(d) < 18:
                continue
            vid = d[8] | (d[9] << 8)
            pid = d[10] | (d[11] << 8)
            if vid not in (0x0F05, 0x04B4, 0x0547, 0x4705):
                continue
            found.append({
                "offset": lo + o,
                "bcdUSB": d[2] | (d[3] << 8),
                "idVendor": vid,
                "idProduct": pid,
                "bcdDevice": d[12] | (d[13] << 8),
                "bNumConfigurations": d[17],
            })
        return found

    def endpoints(self) -> list[dict]:
        _, blob = self._flat()
        eps = {}
        for m in re.finditer(rb"\x07\x05", blob):
            d = blob[m.start():m.start() + 7]
            if len(d) < 7:
                continue
            addr, attr, mx = d[2], d[3], d[4] | (d[5] << 8)
            if attr > 3 or not 1 <= (addr & 0x7F) <= 15:
                continue
            if mx not in (8, 16, 32, 64, 512, 1024):
                continue
            eps[(addr, attr, mx)] = d[6]
        return [
            {"address": a, "dir": "IN" if a & 0x80 else "OUT",
             "type": ["control", "iso", "bulk", "interrupt"][t],
             "max_packet": m, "interval": i}
            for (a, t, m), i in sorted(eps.items())
        ]

    def usb_strings(self) -> list[str]:
        _, blob = self._flat()
        return [s.decode("utf-16-le") for s in
                re.findall(rb"(?:[\x20-\x7e]\x00){4,}", blob)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hexfile")
    ap.add_argument("--segments", action="store_true", help="show memory layout")
    ap.add_argument("--descriptors", action="store_true", help="show USB descriptors")
    ap.add_argument("--chunks", action="store_true", help="show download blocks")
    args = ap.parse_args()

    try:
        img = HexImage.load(args.hexfile)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    segs = img.segments()
    lo, hi = min(img.mem), max(img.mem)
    print(f"{img.path}: {img.total_bytes()} bytes, "
          f"0x{lo:04X}-0x{hi:04X}, {len(segs)} segment(s)")

    if not any((args.segments, args.descriptors, args.chunks)):
        args.segments = args.descriptors = True

    if args.segments:
        print("\nsegments:")
        for a, d in segs:
            note = ""
            if a >= FX2_INTERNAL_RAM_END:
                note = "  << beyond FX2 internal RAM"
            elif a + len(d) > FX2_INTERNAL_RAM_END:
                note = "  << crosses FX2 internal RAM boundary"
            print(f"  0x{a:04X}-0x{a + len(d) - 1:04X}  {len(d):6d} B{note}")

    if args.descriptors:
        print("\nUSB device descriptor(s):")
        for d in img.device_descriptors():
            print(f"  @0x{d['offset']:04X}  {d['idVendor']:04x}:{d['idProduct']:04x}"
                  f"  bcdDevice={d['bcdDevice']:04x}"
                  f"  bcdUSB={d['bcdUSB']:04x}"
                  f"  nCfg={d['bNumConfigurations']}")
        print("\nendpoints:")
        for e in img.endpoints():
            print(f"  0x{e['address']:02X} {e['dir']:3} {e['type']:9} "
                  f"max={e['max_packet']:4} interval={e['interval']}")
        print("\nstrings:", ", ".join(repr(s) for s in img.usb_strings()))

    if args.chunks:
        ch = img.chunked()
        print(f"\ndownload blocks ({len(ch)}):")
        for a, d in ch:
            req = "0xA0 internal" if a < FX2_INTERNAL_RAM_END else "0xA3 external"
            print(f"  0x{a:04X}  {len(d):5d} B  via {req}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
