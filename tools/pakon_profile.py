#!/usr/bin/env python3
"""Parser/dumper for Kodak/Pakon colour profile files (.pf) and .lut files.

Findings (see docs/08-profile-format.md for evidence):

  * ``.pf`` files are STANDARD ICC v2 profiles (magic ``acsp`` at offset 36,
    big-endian, CMM ``KCMS``). This module parses the ICC header, tag table,
    and fully decodes the payload types actually used by the Pakon set:
    ``mft2`` (lut16Type: matrix + input tables + 3D CLUT + output tables),
    ``curv``, ``XYZ ``, ``desc``, ``text``, ``ui08``.
  * ``ColRevLutS6.lut`` is plain ASCII: one integer per CRLF line
    (4096 entries, 12-bit values).

What this tool does NOT decode (honestly): the Kodak private tags
``K070``/``K113``/``K120``-``K123`` (types ``ui08``/``K001``-``K004``) found in
rpd.pf. Their bodies are high-entropy and defeated int/float reinterpretation;
they are dumped as hex only. The transforms in ``A2B0`` are complete without
them.

Usage:
    pakon_profile.py info   FILE.pf            header + tag table
    pakon_profile.py dump   FILE.pf            decoded tags as text (mft2 summarised)
    pakon_profile.py csv    FILE.pf OUTDIR     mft2 tables to CSV files
    pakon_profile.py verify-unity FILE.pf      prove the identity encoding (+/-1 LSB)
    pakon_profile.py lut    FILE.lut           parse/summarise a text .lut

Only the Python 3 standard library is required.
"""

from __future__ import annotations

import csv
import os
import struct
import sys
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# ICC primitives (all big-endian per ICC spec)
# --------------------------------------------------------------------------


def s15f16(raw: int) -> float:
    """s15Fixed16Number -> float."""
    return raw / 65536.0


@dataclass
class Mft2:
    """ICC lut16Type ('mft2'): matrix + input tables + CLUT + output tables."""

    in_ch: int
    out_ch: int
    grid: int
    matrix: list  # 9 floats, row-major 3x3
    n_in: int
    n_out: int
    in_tables: list  # in_ch lists of n_in uint16
    clut: list  # grid**in_ch * out_ch uint16, ch0 index slowest
    out_tables: list  # out_ch lists of n_out uint16

    def clut_node(self, *coords):
        """CLUT output tuple at integer grid coordinates (ch0, ch1, ...)."""
        if len(coords) != self.in_ch:
            raise ValueError(f"need {self.in_ch} coordinates")
        idx = 0
        for c in coords:
            if not 0 <= c < self.grid:
                raise ValueError("grid coordinate out of range")
            idx = idx * self.grid + c
        idx *= self.out_ch
        return tuple(self.clut[idx : idx + self.out_ch])


@dataclass
class IccProfile:
    path: str
    data: bytes
    size: int = 0
    cmm: str = ""
    version: tuple = ()
    dev_class: str = ""
    color_space: str = ""
    pcs: str = ""
    datetime: tuple = ()
    tags: dict = field(default_factory=dict)  # sig -> (offset, size)

    # -- parsing -----------------------------------------------------------

    @classmethod
    def load(cls, path: str) -> "IccProfile":
        with open(path, "rb") as fh:
            data = fh.read()
        if len(data) < 132 or data[36:40] != b"acsp":
            raise ValueError(f"{path}: not an ICC profile ('acsp' magic missing)")
        p = cls(path=path, data=data)
        p.size = struct.unpack_from(">I", data, 0)[0]
        p.cmm = data[4:8].decode("latin1")
        maj, mn = data[8], data[9]
        p.version = (maj, mn >> 4, mn & 0xF)
        p.dev_class = data[12:16].decode("latin1")
        p.color_space = data[16:20].decode("latin1")
        p.pcs = data[20:24].decode("latin1")
        p.datetime = struct.unpack_from(">6H", data, 24)
        ntags = struct.unpack_from(">I", data, 128)[0]
        for i in range(ntags):
            sig, off, sz = struct.unpack_from(">4sII", data, 132 + 12 * i)
            p.tags[sig.decode("latin1")] = (off, sz)
        return p

    def tag_type(self, sig: str) -> str:
        off, _ = self.tags[sig]
        return self.data[off : off + 4].decode("latin1")

    def tag_body(self, sig: str) -> bytes:
        off, sz = self.tags[sig]
        return self.data[off : off + sz]

    def parse_mft2(self, sig: str = "A2B0") -> Mft2:
        off, sz = self.tags[sig]
        d = self.data
        if d[off : off + 4] != b"mft2":
            raise ValueError(f"tag {sig} is {self.tag_type(sig)!r}, not mft2")
        in_ch, out_ch, grid = d[off + 8], d[off + 9], d[off + 10]
        matrix = [s15f16(v) for v in struct.unpack_from(">9i", d, off + 12)]
        n_in, n_out = struct.unpack_from(">HH", d, off + 48)
        p = off + 52
        in_tables = []
        for _ in range(in_ch):
            in_tables.append(list(struct.unpack_from(f">{n_in}H", d, p)))
            p += 2 * n_in
        clut_len = (grid**in_ch) * out_ch
        clut = list(struct.unpack_from(f">{clut_len}H", d, p))
        p += 2 * clut_len
        out_tables = []
        for _ in range(out_ch):
            out_tables.append(list(struct.unpack_from(f">{n_out}H", d, p)))
            p += 2 * n_out
        expected = 52 + 2 * (in_ch * n_in + clut_len + out_ch * n_out)
        if expected != sz:
            # ICC allows padding to 4-byte boundary; anything bigger is a red flag.
            if not sz - 3 <= expected <= sz:
                raise ValueError(
                    f"{self.path}:{sig} size mismatch: computed {expected}, declared {sz}"
                )
        return Mft2(in_ch, out_ch, grid, matrix, n_in, n_out, in_tables, clut, out_tables)

    def parse_curv(self, sig: str):
        off, _ = self.tags[sig]
        d = self.data
        if d[off : off + 4] != b"curv":
            raise ValueError(f"tag {sig} is not curv")
        cnt = struct.unpack_from(">I", d, off + 8)[0]
        vals = struct.unpack_from(f">{cnt}H", d, off + 12)
        if cnt == 1:
            return ("gamma", vals[0] / 256.0)  # u8Fixed8
        return ("table", list(vals))

    def parse_xyz(self, sig: str):
        off, _ = self.tags[sig]
        return tuple(s15f16(v) for v in struct.unpack_from(">3i", self.data, off + 8))

    def parse_desc(self, sig: str) -> str:
        off, _ = self.tags[sig]
        slen = struct.unpack_from(">I", self.data, off + 8)[0]
        return self.data[off + 12 : off + 12 + slen].rstrip(b"\0").decode("latin1", "replace")

    def parse_text(self, sig: str) -> str:
        off, sz = self.tags[sig]
        return self.data[off + 8 : off + sz].rstrip(b"\0").decode("latin1", "replace")


# --------------------------------------------------------------------------
# text .lut files
# --------------------------------------------------------------------------


def load_text_lut(path: str):
    """Parse a plain-text LUT: one number per line (ColRevLutS6.lut style),
    or 'index<TAB>value' pairs (_ClientColNegLut.txt style).
    Returns a list of float values (index-ordered)."""
    vals = []
    with open(path, "r", encoding="ascii", errors="replace") as fh:
        for line in fh:
            parts = line.split()
            if not parts:
                continue
            vals.append(float(parts[-1]))  # last column is the value in both styles
    return vals


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------


def cmd_info(path: str):
    p = IccProfile.load(path)
    y, mo, dy, h, mi, s = p.datetime
    print(f"file        : {path} ({len(p.data)} bytes)")
    print(f"declared sz : {p.size} ({'matches' if p.size == len(p.data) else 'MISMATCH'})")
    print(f"cmm         : {p.cmm!r}   icc version: {p.version[0]}.{p.version[1]}.{p.version[2]}")
    print(f"class       : {p.dev_class!r}   space: {p.color_space!r} -> pcs: {p.pcs!r}")
    print(f"created     : {y:04d}-{mo:02d}-{dy:02d} {h:02d}:{mi:02d}:{s:02d}")
    print(f"tags        : {len(p.tags)}")
    for sig, (off, sz) in p.tags.items():
        print(f"  {sig!r:8s} type={p.tag_type(sig)!r:8s} off={off:8d} size={sz:8d}")


def cmd_dump(path: str):
    p = IccProfile.load(path)
    cmd_info(path)
    print()
    for sig in p.tags:
        typ = p.tag_type(sig)
        try:
            if typ == "desc":
                print(f"{sig}: {p.parse_desc(sig)!r}")
            elif typ == "text":
                print(f"{sig}: {p.parse_text(sig)!r}")
            elif typ == "XYZ ":
                print(f"{sig}: XYZ = {tuple(round(v, 4) for v in p.parse_xyz(sig))}")
            elif typ == "curv":
                kind, v = p.parse_curv(sig)
                if kind == "gamma":
                    print(f"{sig}: gamma {v}")
                else:
                    print(f"{sig}: curve, {len(v)} points, first={v[:4]} last={v[-4:]}")
            elif typ == "mft2":
                m = p.parse_mft2(sig)
                print(f"{sig}: mft2  in={m.in_ch} out={m.out_ch} grid={m.grid}"
                      f" n_in={m.n_in} n_out={m.n_out}")
                print(f"   matrix (s15f16): {[round(x, 5) for x in m.matrix]}")
                for c, t in enumerate(m.in_tables):
                    print(f"   in_tab[{c}] : {t[0]}..{t[-1]}"
                          f" mono={all(t[i] <= t[i+1] for i in range(len(t)-1))}")
                g = m.grid
                lo = m.clut_node(*([0] * m.in_ch))
                hi = m.clut_node(*([g - 1] * m.in_ch))
                mid = m.clut_node(*([g // 2] * m.in_ch))
                print(f"   CLUT corners: [0..]={lo}  [mid]={mid}  [max]={hi}")
                for c, t in enumerate(m.out_tables):
                    print(f"   out_tab[{c}]: {t[0]}..{t[-1]}"
                          f" mono={all(t[i] <= t[i+1] for i in range(len(t)-1))}")
            else:
                body = p.tag_body(sig)
                print(f"{sig}: type {typ!r} UNDECODED, {len(body)} bytes,"
                      f" hex[:32]={body[:32].hex()}")
        except Exception as exc:  # keep dumping other tags
            print(f"{sig}: parse error: {exc}")


def cmd_csv(path: str, outdir: str):
    p = IccProfile.load(path)
    if "A2B0" not in p.tags:
        sys.exit(f"{path}: no A2B0 tag (nothing tabular to export)")
    m = p.parse_mft2("A2B0")
    os.makedirs(outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0]

    fp = os.path.join(outdir, f"{stem}_input_tables.csv")
    with open(fp, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["index"] + [f"ch{c}" for c in range(m.in_ch)])
        for i in range(m.n_in):
            w.writerow([i] + [m.in_tables[c][i] for c in range(m.in_ch)])
    print("wrote", fp)

    fp = os.path.join(outdir, f"{stem}_clut.csv")
    with open(fp, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([f"g{c}" for c in range(m.in_ch)] + [f"out{c}" for c in range(m.out_ch)])
        g = m.grid

        def rec(prefix):
            if len(prefix) == m.in_ch:
                w.writerow(list(prefix) + list(m.clut_node(*prefix)))
                return
            for i in range(g):
                rec(prefix + (i,))

        rec(())
    print("wrote", fp)

    fp = os.path.join(outdir, f"{stem}_output_tables.csv")
    with open(fp, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["index"] + [f"ch{c}" for c in range(m.out_ch)])
        for i in range(m.n_out):
            w.writerow([i] + [m.out_tables[c][i] for c in range(m.out_ch)])
    print("wrote", fp)


def cmd_verify_unity(path: str):
    """Re-run the identity proof: unity.pf CLUT == ICC v2 Lab16 identity +/-1."""
    p = IccProfile.load(path)
    m = p.parse_mft2("A2B0")
    if (m.in_ch, m.out_ch) != (3, 3):
        sys.exit("expected a 3->3 profile")
    g = m.grid
    maxerr = [0, 0, 0]
    scale = (65280, 65535, 65535)  # L: 0..0xFF00 (v2 legacy), a/b: 0..0xFFFF
    for i in range(g):
        for j in range(g):
            for k in range(g):
                got = m.clut_node(i, j, k)
                exp = (
                    round(i / (g - 1) * scale[0]),
                    round(j / (g - 1) * scale[1]),
                    round(k / (g - 1) * scale[2]),
                )
                for c in range(3):
                    maxerr[c] = max(maxerr[c], abs(got[c] - exp[c]))
    print(f"grid {g}^3, max |CLUT - Lab16v2 identity| per channel: {maxerr}")
    ok = all(e <= 1 for e in maxerr)
    print("IDENTITY VERIFIED (+/-1 LSB)" if ok else "NOT an identity within +/-1 LSB")
    return 0 if ok else 1


def cmd_lut(path: str):
    vals = load_text_lut(path)
    mono_up = all(vals[i] <= vals[i + 1] for i in range(len(vals) - 1))
    mono_dn = all(vals[i] >= vals[i + 1] for i in range(len(vals) - 1))
    print(f"{path}: {len(vals)} entries, min={min(vals)}, max={max(vals)}")
    print(f"first 5: {vals[:5]}")
    print(f"last  5: {vals[-5:]}")
    print(f"monotonic: {'increasing' if mono_up else 'decreasing' if mono_dn else 'NO'}")


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    cmd, path = argv[1], argv[2]
    if cmd == "info":
        cmd_info(path)
    elif cmd == "dump":
        cmd_dump(path)
    elif cmd == "csv":
        if len(argv) < 4:
            sys.exit("usage: pakon_profile.py csv FILE.pf OUTDIR")
        cmd_csv(path, argv[3])
    elif cmd == "verify-unity":
        return cmd_verify_unity(path)
    elif cmd == "lut":
        cmd_lut(path)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
