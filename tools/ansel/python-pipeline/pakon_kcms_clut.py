#!/usr/bin/env python3
"""Port of the Kodak CMM's 3-D CLUT interpolator -- ``kodakcms.dll``
``fcn.10018160``, md5 ``e4c8064a9dd3c3a5541d74b00a730e53``.

WHY THIS EXISTS
===============
docs/74 §171 drove the vendor's own CMM under Wine and found this port's
PIL/littleCMS ICC step **not** bit-exact: systematically darker by mean 2.739
sRGB codes with default flags, 1.836 with ``cmsFLAGS_NOOPTIMIZE``. §171.2
ruled out the intent, the profile pair, the data type, ``colorSpaceMax`` and
PCS quantisation, and showed the residual is not a per-channel remap -- it is
a 3-D CLUT interpolation difference. This module closes that by running the
vendor's own interpolation arithmetic instead of lcms's.

THE ROUTINE
===========
``SpEvaluate`` (0x1002ecf0) -> ``PTEvalDT`` (0x10041070) -> fcn.100410a0 ->
fcn.10026d20 -> fcn.10012b30 -> fcn.10012bc0.  fcn.10012bc0 is a pure
dispatcher returning one of 35 evaluator function pointers; the tile loop
fcn.10027410 calls it as ``call dword [ebx + 4]``.

Which one is live was settled **dynamically**, not from naming or proximity:
``kcms_clut_host.exe`` with ``POKE_RVA`` overwrites a candidate's first byte
with ``0xC3`` and re-runs the whole transform.  Exactly one of the 35 changes
SpEvaluate's output -- ``0x10018160`` -- and it sits on the dispatcher's
in=3/out=3 u8 leaf (0x10012f35).

Its whole body (``af``+``pdf``, 799 bytes, no calls) is, per pixel:

    offR, wR = idx[0][r]        # 8-byte records, byte offset + weight
    offG, wG = idx[1][g]
    offB, wB = idx[2][b]
    base = offR + offG + offB

    sort {wR, wG, wB} descending -> (w0, w1, w2), which selects one of six
    tetrahedra and with it two intermediate corner byte offsets (Pa, Pb)

    for ch in 0, 1, 2:
        c = base + 2*ch
        A = clut[c];  C = clut[c + Pa];  B = clut[c + Pb];  D = clut[c + RGB]
        t = (D - B)*w2 + (C - A)*w0 + (B - C)*w1      # signed 32-bit
        out[ch] = otab[ch][ 4*A + (t >> 14) ]         # SAR, i.e. floor

so:

* **Tetrahedral**, not trilinear -- the classic sorted-increment form
  ``A + w0*(C-A) + w1*(B-C) + w2*(D-B)``.
* The grid index and the fraction are NOT computed per pixel. They are read
  out of a 3 x 256 precomputed table (grid+0x8c) that also absorbs any input
  curve. Weights are 16-bit-ish, 0..65535 -- ``idx[c][255].weight`` is 65535,
  **not** 65536, so the top of the input range never reaches the last grid
  node.
* Interpolation happens at **14-bit** precision (``4*A`` plus a ``>>14`` of
  the weighted differences), with an arithmetic shift and therefore
  truncation toward -inf, not round-to-nearest.
* The 14-bit result is then mapped to u8 through a per-channel 16384-entry
  byte table (grid+0x154), so the output transfer curve is exact, not
  interpolated.

The tables themselves are vendor data built by ``SpCombineXforms`` at run
time from ``Rpd2Pcs_HR200_QS_v5s10.pf`` (md5 c1d4f3bba8f06f3427ccfaff5c30b559)
and ``Srgb_v2.pf`` (md5 95bd003685a81450184af6aaf1d0e31c). No closed form is
attempted for them; as with §175's inversion table, byte-exactness comes from
shipping the table. They are captured by the detour in
``tools/re/live_hooks/wine_host/kcms_clut_host.c`` and stored in
``vendor_kcms_rpd2srgb.npz`` next to this file.

STATUS
======
Bit-exact against the real routine over the **entire** u8 RGB input domain --
all 16,777,216 triples, 50,331,648 channel samples, zero differences. See
``pakon_kcms_clut_golden.py``.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

#: Vendor tables captured from the live combined xform.
TABLE_PATH = Path(__file__).resolve().parent / "vendor_kcms_rpd2srgb.npz"

#: Set False to fall back to lcms (e.g. if the table file is absent).
KCMS_CLUT_PORTED = True

_CACHE: dict[str, object] | None = None


# --------------------------------------------------------------------------
# table loading / packing
# --------------------------------------------------------------------------
def pack(dump_dir: str | Path, out: str | Path = TABLE_PATH) -> Path:
    """Pack a ``kcms_clut_host.exe DUMP_DIR`` capture into the npz."""
    d = Path(dump_dir)
    meta: dict[str, int] = {}
    for line in (d / "grid_meta.txt").read_text().splitlines():
        p = line.split()
        if len(p) == 2:
            meta[p[0]] = int(p[1])
    idx = np.frombuffer((d / "idxtab.bin").read_bytes(), dtype="<i4")
    idx = idx.reshape(3, 256, 2).copy()
    clut = np.frombuffer((d / "clut.bin").read_bytes(), dtype="<u2").copy()
    otab = np.frombuffer((d / "otab.bin").read_bytes(), dtype=np.uint8)
    otab = otab.reshape(3, 0x4000).copy()
    corners = np.array([meta["offB"], meta["offG"], meta["offGB"],
                        meta["offR"], meta["offRB"], meta["offRG"],
                        meta["offRGB"]], dtype=np.int64)
    out = Path(out)
    np.savez_compressed(out, idx=idx, clut=clut, otab=otab, corners=corners,
                        gridN=np.int64(meta["gridN"]))
    return out


def tables() -> dict:
    """Load (and cache) the vendor tables."""
    global _CACHE
    if _CACHE is None:
        z = np.load(TABLE_PATH)
        c = z["corners"].astype(np.int64)
        _CACHE = {
            "idx": z["idx"].astype(np.int64),
            "clut": z["clut"].astype(np.int64),
            "otab": z["otab"],
            "offB": int(c[0]), "offG": int(c[1]), "offGB": int(c[2]),
            "offR": int(c[3]), "offRB": int(c[4]), "offRG": int(c[5]),
            "offRGB": int(c[6]), "gridN": int(z["gridN"]),
        }
    return _CACHE


def available() -> bool:
    return KCMS_CLUT_PORTED and TABLE_PATH.is_file()


# --------------------------------------------------------------------------
# the evaluator
# --------------------------------------------------------------------------
#: pixels per chunk -- the intermediates are ~15 int64 planes, so a whole
#: 16.7 M-pixel exhaustive sweep would need several GB in one go.
CHUNK = 1 << 21


def evaluate(rgb_u8: np.ndarray, t: dict | None = None) -> np.ndarray:
    """``fcn.10018160`` on interleaved RGB u8. Shape (..., 3) in and out."""
    if t is None:
        t = tables()
    a = np.asarray(rgb_u8, dtype=np.uint8)
    shape = a.shape
    flat = a.reshape(-1, 3)
    if flat.shape[0] > CHUNK:
        out = np.empty_like(flat)
        for i in range(0, flat.shape[0], CHUNK):
            out[i:i + CHUNK] = _eval_chunk(flat[i:i + CHUNK], t)
        return out.reshape(shape)
    return _eval_chunk(flat, t).reshape(shape)


def _eval_chunk(flat: np.ndarray, t: dict) -> np.ndarray:
    n = flat.shape[0]

    idx, clut, otab = t["idx"], t["clut"], t["otab"]
    oB, oG, oGB = t["offB"], t["offG"], t["offGB"]
    oR, oRB, oRG = t["offR"], t["offRB"], t["offRG"]
    oRGB = t["offRGB"]

    r = flat[:, 0].astype(np.int64)
    g = flat[:, 1].astype(np.int64)
    b = flat[:, 2].astype(np.int64)

    base = idx[0, r, 0] + idx[1, g, 0] + idx[2, b, 0]      # byte offset
    fr, fg, fb = idx[0, r, 1], idx[1, g, 1], idx[2, b, 1]

    # the disassembly's three signed compares, in its own order:
    #   0x100182a4 cmp fr,fg / 0x100182ac cmp fg,fb / 0x100182c9 cmp fr,fb
    rg = fr > fg
    gb = fg > fb
    rb = fr > fb

    w0 = np.empty(n, np.int64)
    w1 = np.empty(n, np.int64)
    w2 = np.empty(n, np.int64)
    Pa = np.empty(n, np.int64)
    Pb = np.empty(n, np.int64)

    for mask, (a0, a1, a2, pa, pb) in (
            (rg & gb,        (fr, fg, fb, oR, oRG)),   # fr > fg > fb
            (rg & ~gb & rb,  (fr, fb, fg, oR, oRB)),   # fr > fb >= fg
            (rg & ~gb & ~rb, (fb, fr, fg, oB, oRB)),   # fb >= fr > fg
            (~rg & gb & ~rb, (fg, fb, fr, oG, oGB)),   # fg > fb >= fr
            (~rg & gb & rb,  (fg, fr, fb, oG, oRG)),   # fg >= fr > fb
            (~rg & ~gb,      (fb, fg, fr, oB, oGB))):  # fb >= fg >= fr
        w0[mask] = a0[mask]
        w1[mask] = a1[mask]
        w2[mask] = a2[mask]
        Pa[mask] = pa
        Pb[mask] = pb

    out = np.empty((n, 3), np.uint8)
    for ch in range(3):
        c = base + 2 * ch
        A = clut[c >> 1]
        C = clut[(c + Pa) >> 1]
        B = clut[(c + Pb) >> 1]
        D = clut[(c + oRGB) >> 1]
        tt = (D - B) * w2 + (C - A) * w0 + (B - C) * w1
        tt = ((tt + 2 ** 31) % 2 ** 32) - 2 ** 31          # 32-bit signed wrap
        out[:, ch] = otab[ch][4 * A + (tt >> 14)]          # SAR 14 == floor
    return out


if __name__ == "__main__":                                  # pragma: no cover
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == "pack":
        print("wrote", pack(sys.argv[2]))
    else:
        t = tables()
        print(f"grid {t['gridN']}^3, corners B={t['offB']} G={t['offG']} "
              f"R={t['offR']} RGB={t['offRGB']}")
        print("clut u16 range %d..%d" % (t["clut"].min(), t["clut"].max()))
