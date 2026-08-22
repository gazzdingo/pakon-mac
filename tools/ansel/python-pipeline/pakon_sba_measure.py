#!/usr/bin/env python3
"""Port of ``fcn.102aece0`` (``PakonIMAu.dll``) — the SBA measuring pass.

``fcn.102aece0`` is the producer of everything the SBA statistics vector
carries: it walks a 24x36x6 sample grid and fills the five argument blocks
that ``fcn.102b7440`` (already bit-exact, docs/74 §192.3) packs into the
720-slot vector at ``obj+0x3c``, plus the **864-byte per-sample selection
mask** at ``obj+0xc20`` that §76.4's weighted-mean chroma residual walks to
make U and V.

**This port is PARTIAL.**  What is implemented is listed in
:data:`PORTED`; what is not is listed in :data:`NOT_PORTED`.  Nothing here
should be read as a claim about the parts that are absent.  Every claim the
implemented part makes is checked byte-for-byte against the real DLL run
whole under Unicorn by ``pakon_sba_measure_golden.py``.

Geometry (derived, not assumed)
-------------------------------
``0x102afb60`` computes six plane bases as ``(9r + k) * 4`` for
``k = 0, 0xd8, 0x1b0, 0x288, 0x360, 0x438`` — i.e. word offsets
``864 * p`` — with the row loop bounded by ``0x102b136d cmp eax,0x18`` (24)
and the column loop by ``0x102b1353 cmp ecx,0x24`` (36).  So the sample
buffer is 6 planes x 24 rows x 36 cols of ``int16``, plane-major, row
stride 36, plane stride 864, and ``0x102aeda3`` seeds the count block with
``0x360`` = 864 outright.

Each band sample has one of ``arg2``'s six ``int32`` subtracted from it
(``0x102afbe6`` / ``0x102afbf9`` / ``0x102afc0a`` and the three siblings).

The per-sample tables
---------------------
``arg3`` (0..7) picks one of five ``.data`` byte tables **and** one of four
``.data`` dword tables (``0x102af1da … 0x102af259``); both are walked one
entry per sample by ``0x102b1346`` (``+4`` dword / ``+1`` byte), never
reset across rows, so their index is the linear ``36*r + c``.  Their sizes
follow from that: 864 bytes and 864 dwords, which is exactly the spacing
between consecutive table addresses.  They are read out of the DLL image
here — the same status as any other shipped vendor LUT.

Where the rest of the function is, for whoever finishes it
----------------------------------------------------------
The frame is ``0xfac + 0x10`` bytes and ESP is constant through the whole
body, so every ``[esp + d]`` displacement in the listing IS the frame
offset — no fixups, except inside the ten pushes of the tail call.  The
five output blocks live at ``+0x2a8`` (A7), ``+0x2d0`` (A5), ``+0x2f4``
(A4), ``+0x344`` (A6) and ``+0xe84`` (A3); the 26 histogram descriptors are
at ``+0x64``, stride ``0x14``, laid out ``{bins*, nbins, bias, scale,
count}`` and binned as ``clamp((v + bias)/scale, 0, nbins-1)``
(``0x102afefb … 0x102aff28``).

* Four straight-line constant-init runs fill the frame before any sample is
  read: ``0x102aece0-0x102af132`` (147 stores), ``0x102af364-0x102af754``
  (144, taken only when ``word[en+0x0e] != 0``), ``0x102af764-0x102af83a``
  (29) and ``0x102af840-0x102afa38`` (72, skipped when ``arg5 == 1``, which
  is also why that mode leaves the histogram pointers NULL and the caller
  must clear ``en[0x10..0x13]``).  All 392 are plain ``mov`` with register
  constants and fall out of a linear symbolic pass over the instruction
  stream — they do not need reading by hand.
* The per-sample body is ``0x102afb60-0x102b1374``.  ``arg7``'s words 0..6
  carry 14 zone gates as bytes; the per-sample dword from the arg3 table
  picks ONE of 13 ``(zone, half)`` banks by its lowest set bit (bit ``k`` ->
  zone ``(k+1)//2``, half ``(k+1)%2``), and ``(zone 0, half 0)`` is
  accumulated unconditionally.  A bank is ``min`` at ``A6 + 0x120*i +
  0x90*b + 0x00``, ``max`` at ``+0x18``, ``sum`` at ``+0x30``, six int32
  each, initialised to 10000 / -10000 / 0 — which is exactly the layout
  `pakon_orderfpo_vecpack` reads from the other side.
"""
from __future__ import annotations

import struct
from pathlib import Path

PAKONIMAU_MD5 = "eea9dcf78ee21d4f7c515a6c2512242d"
DEFAULT_DLL = (
    Path(__file__).resolve().parents[2] / "re" / "live_hooks" / "wine_host" / "PakonIMAu.dll"
)
IMAGE_BASE = 0x10000000

N_BANDS, N_ROWS, N_COLS = 6, 24, 36
N_SAMPLES = N_ROWS * N_COLS          # 864
PLANE_STRIDE = N_SAMPLES

#: what this module reproduces bit-exactly against the real DLL
PORTED = (
    "the 24x36x6 sample grid and the six arg2 offsets",
    "the arg3 -> (byte table, dword table) selector at 0x102af1da",
    "the 864-byte selection mask at obj+0xc20, both of its stages",
)
#: what it does not
NOT_PORTED = (
    "A6 — the 0xb00 bank block (14 banks of min/max/sum over 6 bands, "
    "plus the four whole-frame banks)",
    "A3 / A4 / A5 — the 75 / 19 / 9 dword blocks",
    "A7 — the count block beyond its 0x360 seed",
    "the 26 calloc'd histograms and every percentile derived from them",
    "the object header words at +0x06..+0x1c",
)

#: ``arg3`` -> (byte table VA, dword table VA), read off ``0x102af1da…0x102af259``.
#: Five byte tables 0x360 apart, four dword tables 0xd80 apart — 864 entries each.
SEL_TABLES = {
    0: (0x105A8E10, 0x1069E5A0), 4: (0x105A8E10, 0x1069E5A0),
    1: (0x105A94D0, 0x106A00A0), 5: (0x105A94D0, 0x106A00A0),
    2: (0x105A9170, 0x1069F320), 6: (0x105A9170, 0x1069F320),
    3: (0x105A9830, 0x106A0E20), 7: (0x105A9830, 0x106A0E20),
}
#: the ``0x102af210`` default arm, taken for any arg3 outside 0..7
SEL_DEFAULT = (0x105A9B90, 0x1069F320)

#: ``0x102b0b08 mov eax, dword [0x106bc820]`` — the only reference to this
#: address anywhere in the 24 MB image (byte-scanned), and its static
#: initialiser is 0.  Nothing in this DLL writes it, so the white-balanced
#: hue arm at ``0x102b0b15…0x102b0d95`` is dead in this build and the
#: ``0x102b0e75`` raw-band arm is the one that runs.  Exposed as a parameter
#: so the golden can prove the branch is live rather than vacuous.
HUE_WB_GLOBAL = 0x106BC820

#: ``0x102af145`` — arg6 selects four parameter-struct word quads.
#: (hue_lo, hue_hi, chroma_lo, chroma_hi) offsets into ``par``.
MODE_PARAMS = {
    2: (0x4A, 0x4C, 0x46, 0x48),
    1: (0x52, 0x54, 0x4E, 0x50),
    8: (0x3A, 0x3C, 0x36, 0x38),
    4: (0x42, 0x44, 0x3E, 0x40),
}

#: ``0x102b0a2d lea eax,[arg1 + ecx*2 + 0x13f6]`` — the 3x3 local-contrast
#: window is centred 2592 words into the buffer, i.e. on plane 3, and its
#: base is that centre minus one row minus one column.  ``0x13f6`` is
#: 5110 bytes = 2555 words = 2592 - 36 - 1.  There is no bounds check: at
#: ``r == 0`` the "row above" is plane 2's last row, and the vendor's own
#: arithmetic is reproduced rather than corrected.
WINDOW_BASE = 0x13F6 // 2            # 2555
WINDOW_ROW = N_COLS                  # 36 words


class MeasureFault(RuntimeError):
    """Raised where the DLL would fault (``idiv`` by zero, null histogram)."""


def _i16(v: int) -> int:
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def _i32(v: int) -> int:
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v & 0x80000000 else v


def _idiv(n: int, d: int) -> int:
    """x86 ``idiv``: quotient truncated toward zero."""
    if d == 0:
        raise MeasureFault("idiv by zero")
    q = abs(n) // abs(d)
    return -q if (n < 0) != (d < 0) else q


def _sar1(v: int) -> int:
    """``sar reg,1`` — arithmetic shift, i.e. floor division by two."""
    return v >> 1


# ------------------------------------------------------- the vendor's tables

_TABLE_CACHE: dict = {}


def load_tables(dll_path=None):
    """Read the five byte tables and four dword tables out of the DLL image."""
    path = Path(dll_path or DEFAULT_DLL)
    key = str(path)
    if key in _TABLE_CACHE:
        return _TABLE_CACHE[key]
    pe = path.read_bytes()
    e = struct.unpack_from("<I", pe, 0x3C)[0]
    nsec = struct.unpack_from("<H", pe, e + 6)[0]
    optsz = struct.unpack_from("<H", pe, e + 20)[0]
    opt = e + 24
    img = bytearray(struct.unpack_from("<I", pe, opt + 56)[0])
    so = opt + optsz
    for i in range(nsec):
        o = so + i * 40
        vsz, va, rsz, raddr = struct.unpack_from("<IIII", pe, o + 8)
        if rsz == 0 or raddr == 0:
            continue
        d = pe[raddr:raddr + rsz][:max(vsz, rsz)]
        img[va:va + len(d)] = d
    out = {}
    for va in {a for a, _ in SEL_TABLES.values()} | {SEL_DEFAULT[0]}:
        o = va - IMAGE_BASE
        out[va] = bytes(img[o:o + N_SAMPLES])
    for va in {b for _, b in SEL_TABLES.values()} | {SEL_DEFAULT[1]}:
        o = va - IMAGE_BASE
        out[va] = list(struct.unpack_from("<%dI" % N_SAMPLES, bytes(img), o))
    out["global_%x" % HUE_WB_GLOBAL] = struct.unpack_from(
        "<I", bytes(img), HUE_WB_GLOBAL - IMAGE_BASE)[0]
    _TABLE_CACHE[key] = out
    return out


# ------------------------------------------------------------ the hue wheel


def hue_code(s0: int, s1: int, s2: int) -> int:
    """``0x102b0e75 … 0x102b0f97`` — a 120-step hue wheel over three bands.

    Six sextants with bases 1 / 0x15 / 0x29 / 0x3d / 0x51 / 0x65, each
    spanning 20; every arm ends at ``0x102b0f89 cmp eax,0x79`` which maps a
    result of 0x79 or more back to 1, as does every arm that matches no
    sextant at all.  The ``+ (den >> 1)`` before the ``idiv`` is the
    vendor's round-to-nearest; ``sar`` (not ``shr``) is what the DLL uses,
    so it floors on negatives.
    """
    h = 1
    if s0 == s1 and s1 == s2:
        return 1
    if s0 >= s1 and s1 >= s2:
        den = s0 - s2
        h = 0x01 + _idiv(_sar1(den) + 20 * (s0 - s1), den)
    elif s0 > s2 and s2 > s1:
        den = s0 - s1
        h = 0x15 + _idiv(_sar1(den) + 20 * (s2 - s1), den)
    elif s2 >= s0 and s0 >= s1:
        den = s2 - s1
        h = 0x29 + _idiv(_sar1(den) + 20 * (s2 - s0), den)
    elif s2 > s1 and s1 > s0:
        den = s2 - s0
        h = 0x3D + _idiv(_sar1(den) + 20 * (s1 - s0), den)
    elif s1 >= s2 and s2 >= s0:
        den = s1 - s0
        h = 0x51 + _idiv(_sar1(den) + 20 * (s1 - s2), den)
    elif s1 > s0 and s0 > s2:
        den = s1 - s2
        h = 0x65 + _idiv(_sar1(den) + 20 * (s0 - s2), den)
    else:
        return 1
    return h if h < 0x79 else 1


# ----------------------------------------------------------------- the mask


def selection_mask(image, offsets, *, sel, mode, mode_pack, en, par, obj,
                   tables=None, dll_path=None):
    """Fill ``obj[0xc20 : 0xc20+864]`` exactly as ``fcn.102aece0`` does.

    ``obj`` is mutated in place and returned.  Bytes the DLL does not store
    are left untouched, so a poison fill survives wherever the vendor is
    silent — which is how the golden distinguishes "wrote 0" from "did not
    write".
    """
    tables = tables or load_tables(dll_path)
    tab_a, tab_b = SEL_TABLES.get(sel & 0xFFFF, SEL_DEFAULT)
    ta = tables[tab_a]

    # `0x102b09d7 … 0x102b09e7` — the mask block runs at all only if one of
    # these three is set; otherwise `je 0x102b124e` skips it for every sample.
    if not (en[0x0E] or (en[0x0F] & 0x40) or (en[0x14] & 0x40)):
        return obj

    a5 = mode_pack & 0xFFFF
    thr = _i16(struct.unpack_from("<H", par, 0x0C)[0])   # 0x102af13d
    hue_lo_o, hue_hi_o, c_lo_o, c_hi_o = MODE_PARAMS[mode]
    hue_lo = _i16(struct.unpack_from("<H", par, hue_lo_o)[0])
    hue_hi = _i16(struct.unpack_from("<H", par, hue_hi_o)[0])
    # `0x102af261 … 0x102af26f` squares both chroma limits
    c_lo = _i32(_i16(struct.unpack_from("<H", par, c_lo_o)[0]) ** 2)
    c_hi = _i32(_i16(struct.unpack_from("<H", par, c_hi_o)[0]) ** 2)
    bias = _i16(struct.unpack_from("<H", par, 0x56)[0])   # -> [esp+0x288]
    slot479 = _i32(struct.unpack_from("<I", bytes(obj), 0x7B8)[0])
    wb_global = tables["global_%x" % HUE_WB_GLOBAL]

    for r in range(N_ROWS):
        for c in range(N_COLS):
            idx = N_COLS * r + c
            band = [_i32(image[PLANE_STRIDE * p + idx] - offsets[p])
                    for p in range(N_BANDS)]
            a = ta[idx]

            # -- stage 1: local contrast on plane 3 -----------------------
            if a5 != 2:
                if a == 0:
                    obj[0xC20 + idx] = 0
                else:
                    base = idx + WINDOW_BASE
                    mn = mx = image[base]
                    for k in range(3):
                        for row in (0, WINDOW_ROW, 2 * WINDOW_ROW):
                            v = image[base + row + k]
                            if v < mn:
                                mn = v
                            elif v > mx:
                                mx = v
                    obj[0xC20 + idx] = 1 if (mx - mn) > thr else 0

            # -- stage 2: the hue/chroma window sets bit 1 ----------------
            if a5 == 1 or a == 0:
                continue
            b = obj[0xC20 + idx]
            if b == 1:
                continue
            if wb_global:
                raise MeasureFault(
                    "the white-balanced hue arm at 0x102b0b15 is not ported; "
                    "it is dead in the shipped build (%#x == 0)" % HUE_WB_GLOBAL)
            chroma2 = _i32(band[4] * band[4] + band[5] * band[5])
            h = hue_code(band[0], band[1], band[2])
            if band[3] < _i32(slot479 + bias):
                continue
            if h <= hue_lo or h >= hue_hi:
                continue
            if chroma2 <= c_lo or chroma2 >= c_hi:
                continue
            obj[0xC20 + idx] = b | 2
    return obj


def measure(*, image, offsets, sel, arg4, mode_pack, mode, en, par, aim, obj,
            dll_path=None):
    """Partial ``fcn.102aece0``.  Returns the blocks this port produces.

    Absent keys mean "not ported", not "all zero" — the golden reports them
    as unported rather than scoring them.
    """
    if mode not in MODE_PARAMS:
        return {"ret": 0x189C, "obj": bytes(obj)}      # 0x102b4ca3
    selection_mask(image, offsets, sel=sel, mode=mode, mode_pack=mode_pack,
                   en=en, par=par, obj=obj, dll_path=dll_path)
    return {
        "ret": 0,
        "obj": bytes(obj),
        "mask": bytes(obj[0xC20:0xC20 + N_SAMPLES]),
    }
