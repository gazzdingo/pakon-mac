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
    "A6 — the 14 zone/half banks' min/max/sum (the 3-pass, lowest-set-bit "
    "bank selection; per-band gate en[n]) AND the whole-frame bank the L-term "
    "consumes (mask==1 min/max/sum, band3*selbyte special sum, band3^2>>5 "
    "row, band3*selbyte over dword&0x10)",
    "A7 — the per-bank sample-count block (words 0..13) and the whole-frame "
    "counts (words 0x1c/0x1e = mask==1 count, 0x20/0x22 = mask==1&dword&0x10)",
    "the object header words +0x06 (mask==1 count), +0x08 (sum selbyte over "
    "mask==1), +0x0a (mask==1&dword&0x10 count), +0x0c (sum selbyte over that)",
    "the four live histograms (band0 all; band3 all / over-bank5 / over-mask1) "
    "and the A3 percentiles, A5[0] mode and A4[12,13] mean-of-bins>=2 the "
    "L-term reads from them",
    "the assembled L-input vector: every obj+0x3c slot the pcode L-term reads "
    "reproduces the captured vector bit-exact, and L / orderFpo / the per-frame "
    "balance triple A match the real vendor 6/6 on the closecolor cap.pkl frames",
)
#: what it does not
NOT_PORTED = (
    "A6 row4/row5/scalar rows and whole-frame banks OTHER than the ones the "
    "L-term reads (they feed non-L vector slots only)",
    "A3 / A4 / A5 entries OTHER than the 7 / 2 / 1 the L-term consumes",
    "the 22 histograms that stay empty for these frames (gated off) and every "
    "percentile the L-term does not read",
    "the object header words +0x0e..+0x1c",
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


# =====================================================================
# The statistics blocks the pcode L-term consumes
# =====================================================================
#
# The p-code ``L`` term (the whole per-frame variation of ``orderFpo.Y``, the
# blocker docs/74 §192.6 named) reads 41 of ``obj+0x3c``'s slots
# below 720, which ``fcn.102b7440`` (``pakon_orderfpo_vecpack``) packs from five
# blocks ``fcn.102aece0`` fills — A3 (``+0xe84``), A4 (``+0x2f4``), A5
# (``+0x2d0``), A6 (``+0x344``), A7 (``+0x2a8``) — plus four object header
# words.  This section ports exactly the arithmetic behind those 41 slots,
# verified bit-exact against the whole-function Unicorn golden (``run_dll``) and
# against the six real vendor frames in ``cap.pkl``.
#
# The per-sample bank engine (A6 + A7), disassembly-derived
# ---------------------------------------------------------
# Three passes walk the 24x36 grid.  Bank 0 (``A6+0``) accumulates every
# sample; the arg3-selected dword table's set bits pick at most one further
# bank per pass — the LOWEST set bit within that pass's bit range:
#   pass 1  bits 0..4 -> banks 1..5     (``0x102afdd1`` chain)
#   pass 2  bits 5..8 -> banks 6..9     (``0x102b13b0`` re-walk)
#   pass 3  bits 9..12 -> banks 10..13  (``0x102b1ba?`` re-walk)
# Bank ``n`` base = ``0x120*(n//2) + 0x90*(n%2)``; its min/max/sum rows are at
# ``+0x00 / +0x18 / +0x30`` (six int32, init 10000 / -10000 / 0); band ``p`` is
# accumulated iff bit ``p`` of the gate byte ``en[n]`` is set.  A7 word ``n`` is
# that bank's sample count (``0x102b21..`` writes them from the counters).

_A6_LEN = 0x0B00
_A7_LEN = 0x28
_A3_LEN, _A4_LEN, _A5_LEN = 0x4B * 4, 0x13 * 4, 9 * 4

#: A7 words 0..13 — the per-bank divisors.  These are hard-coded IMMEDIATES in
#: ``fcn.102aece0``'s prologue (``0x102aece7 mov eax,0xa2`` = 162,
#: ``0x102aed19 mov eax,0xd8`` = 216, ``0x102aeda3 … 0x360`` = 864), NOT runtime
#: counts.  For the shipped (balanced) selector table they equal the actual
#: per-bank selection counts — each pass's banks sum to 864 — which is why the
#: real frames matched both readings; the DLL writes these constants regardless
#: of the arg3 table, so the port uses the constants.
A7_BANK_DIVISORS = (864, 162, 162, 162, 162,
                    216, 216, 216, 216, 216, 216, 216, 216, 216)

#: The four histograms that are non-empty for the closecolor scan config.  Their
#: descriptors are hard-coded IMMEDIATES in ``fcn.102aece0`` (``0x102aed94``
#: ``mov edi,0x190`` = nbins 400, ``mov edx,0x514`` = bias 1300, ``mov ecx,0x19``
#: = scale 25; ``0x1f4`` = 500 / ``0xa`` = 10 / ``0x3e8`` = 1000 for the band0
#: one) — vendor constants, not ``par``-derived.  ``sel`` = which band, ``pop``
#: = which sample subset.  Verified bit-exact vs the DLL-dumped histograms 6/6.
_HISTS = {
    0:  dict(band=0, subset="all",   nbins=500, bias=1000, scale=10),
    8:  dict(band=3, subset="all",   nbins=400, bias=1300, scale=25),
    13: dict(band=3, subset="bank5", nbins=400, bias=1300, scale=25),
    14: dict(band=3, subset="mask1", nbins=400, bias=1300, scale=25),
}

#: L's A3 entries -> (histogram id, percentile fraction k in %), read off the
#: extraction chain at ``0x102b223b…`` (``target = trunc((k*total+50)/100)``).
_A3_PERCENTILES = {1: (8, 10), 10: (8, 50), 18: (8, 90),
                   22: (14, 50), 26: (13, 10), 29: (0, 10), 52: (0, 95)}
#: A5[0] is the MODE of histogram 8 (``0x102b496e``); A4[12]/A4[13] are the
#: "mean of bins with count>=2" statistic (``0x102b3cb2`` / ``0x102b45..``) of
#: histograms 13 / 0 respectively.
_A5_MODE = {0: 8}
_A4_MEAN_GE2 = {12: 13, 13: 0}


def _lowest_set_bit_in(x, bits):
    for k in bits:
        if x & (1 << k):
            return k
    return None


def _bank_base(n):
    return 0x120 * (n // 2) + 0x90 * (n % 2)


def _tdiv(n, d):
    """x86 ``idiv`` truncation toward zero (also the ``imul magic`` idiom)."""
    q = abs(n) // abs(d)
    return q if (n < 0) == (d < 0) else -q


def _binidx(v, bias, scale, nbins):
    """``0x102afefb`` bin: ``clamp((v+bias)/scale, 0, nbins-1)`` (idiv trunc)."""
    b = _tdiv(v + bias, scale)
    return 0 if b < 0 else (nbins - 1 if b > nbins - 1 else b)


def _bands(image, offsets, idx):
    return [_i32(image[PLANE_STRIDE * p + idx] - offsets[p])
            for p in range(N_BANDS)]


def measure_bank_block(image, offsets, *, sel, en, dll_path=None):
    """A6 14-bank min/max/sum region + A7 per-bank counts (words 0..13).

    Returns ``(A6: bytearray(0xb00), counts: list[14])``.  Bit-exact vs the DLL
    over the 14 banks' min/max/sum rows (row4/row5/scalars are left 0 — they
    feed no L slot).
    """
    tables = load_tables(dll_path)
    _, tab_b = SEL_TABLES.get(sel & 0xFFFF, SEL_DEFAULT)
    dwords = tables[tab_b]
    A6 = bytearray(_A6_LEN)
    counts = [0] * 14

    def setd(off, v):
        struct.pack_into("<i", A6, off, _i32(v))

    def getd(off):
        return struct.unpack_from("<i", A6, off)[0]

    for n in range(14):                          # init gated by en[n] != 0
        if en[n] == 0:
            continue
        b = _bank_base(n)
        for j in range(6):
            setd(b + 0x00 + 4 * j, 10000)
            setd(b + 0x18 + 4 * j, -10000)

    def accumulate(n, band):
        gate = en[n]
        if gate == 0:
            return
        counts[n] += 1
        b = _bank_base(n)
        for p in range(6):
            if gate & (1 << p):
                v = band[p]
                if getd(b + 0x00 + 4 * p) > v:
                    setd(b + 0x00 + 4 * p, v)
                if getd(b + 0x18 + 4 * p) < v:
                    setd(b + 0x18 + 4 * p, v)
                setd(b + 0x30 + 4 * p, getd(b + 0x30 + 4 * p) + v)

    for idx in range(N_SAMPLES):
        band = _bands(image, offsets, idx)
        dw = dwords[idx]
        accumulate(0, band)
        for rng in (range(0, 5), range(5, 9), range(9, 13)):
            k = _lowest_set_bit_in(dw, rng)
            if k is not None:
                accumulate(k + 1, band)
    return A6, counts


def measure_whole_frame(A6, image, offsets, mask, *, sel, en, dll_path=None):
    """Fill the whole-frame bank the L-term reads, into ``A6`` (mutated).

    ``0x102b0fb4``: for every ``mask==1`` sample, band ``p`` (gate ``en[0x0e]``
    low byte) -> bank0 @ ``0x7e0`` min/max/sum; band3 also -> special sum
    ``0x8ac`` (of ``band3*selbyte``), ``band3^2>>5`` row ``0x834`` (gate
    ``en[0x14]&0x40``); over ``mask==1 & dword&0x10`` a ``band3*selbyte`` sum
    goes to ``0x9cc``.  Returns the four header counters as a dict.
    """
    tables = load_tables(dll_path)
    tab_a, tab_b = SEL_TABLES.get(sel & 0xFFFF, SEL_DEFAULT)
    bytetab, dwords = tables[tab_a], tables[tab_b]

    def setd(off, v):
        struct.pack_into("<i", A6, off, _i32(v))

    def getd(off):
        return struct.unpack_from("<i", A6, off)[0]

    WF = 0x7E0
    en0e = struct.unpack_from("<H", bytes(en), 0x0E)[0]
    lo = en0e & 0xFF
    en14 = struct.unpack_from("<H", bytes(en), 0x14)[0] & 0xFF
    if en0e != 0:
        for j in range(6):
            setd(WF + 0x00 + 4 * j, 10000)
            setd(WF + 0x18 + 4 * j, -10000)
    hdr = dict(n_mask1=0, sum_sel_m1=0, n_m1_b4=0, sum_sel_m1_b4=0)

    for idx in range(N_SAMPLES):
        if mask[idx] != 1:
            continue
        band = _bands(image, offsets, idx)
        selbyte = bytetab[idx]
        if selbyte & 0x80:
            selbyte -= 0x100                    # movsx byte
        ebp = _i32(band[3] * selbyte)
        dw = dwords[idx]
        hdr["n_mask1"] += 1
        hdr["sum_sel_m1"] += selbyte
        for p in range(6):
            if lo & (1 << p):
                v = band[p]
                if getd(WF + 0x00 + 4 * p) > v:
                    setd(WF + 0x00 + 4 * p, v)
                if getd(WF + 0x18 + 4 * p) < v:
                    setd(WF + 0x18 + 4 * p, v)
                setd(WF + 0x30 + 4 * p, getd(WF + 0x30 + 4 * p) + v)
                if p == 3:
                    setd(0x8AC, getd(0x8AC) + ebp)
        if en14 & 0x40:
            setd(0x834, getd(0x834) + ((band[3] * band[3]) >> 5))
        if dw & 0x10:
            setd(0x9CC, getd(0x9CC) + ebp)
            hdr["n_m1_b4"] += 1
            hdr["sum_sel_m1_b4"] += selbyte
    return hdr


def build_histograms(image, offsets, mask, *, sel, dll_path=None):
    """The four non-empty histograms as ``{id: (hist, nbins, scale, bias, total)}``."""
    tables = load_tables(dll_path)
    _, tab_b = SEL_TABLES.get(sel & 0xFFFF, SEL_DEFAULT)
    dwords = tables[tab_b]
    out = {}
    for hid, spec in _HISTS.items():
        out[hid] = ([0] * spec["nbins"], spec["nbins"], spec["scale"],
                    spec["bias"], 0)
    for idx in range(N_SAMPLES):
        band = _bands(image, offsets, idx)
        low04 = _lowest_set_bit_in(dwords[idx], range(0, 5))
        for hid, spec in _HISTS.items():
            if spec["subset"] == "bank5" and low04 != 4:
                continue
            if spec["subset"] == "mask1" and mask[idx] != 1:
                continue
            hist, nbins, scale, bias, _ = out[hid]
            hist[_binidx(band[spec["band"]], bias, scale, nbins)] += 1
    return {hid: (h, nb, sc, bi, sum(h)) for hid, (h, nb, sc, bi, _) in out.items()}


def _percentile(hd, k):
    hist, nbins, scale, bias, total = hd
    target = _tdiv(k * total + 50, 100) & 0xFFFF
    if target & 0x8000:
        target -= 0x10000                       # movsx ax
    cum = ecx = 0
    if target > 0:
        while ecx < nbins:
            cum += hist[ecx]
            ecx += 1
            if cum >= target:
                break
    return (ecx - 1) * scale - bias


def _mode(hd):
    hist, nbins, scale, bias, _ = hd
    best_c = best_i = 0
    for i in range(nbins):
        if hist[i] > best_c:                     # first strict argmax
            best_c, best_i = hist[i], i
    return best_i * scale - bias


def _mean_ge2(hd):
    hist, nbins, scale, bias, _ = hd
    S = C = 0
    for i in range(nbins):
        if hist[i] >= 2:
            C += 1
            S += i
    if C == 0:
        return 0
    mean1000 = _tdiv(S * 1000 + (C >> 1), C)     # round(S*1000/C), half up
    x = mean1000 * scale
    return _tdiv(x + (500 if x >= 0 else -500), 1000) - bias


def measure_l_blocks(*, image, offsets, sel, en, par, obj, mode, mode_pack,
                     dll_path=None):
    """Every ``fcn.102aece0`` output byte the pcode ``L`` term consumes.

    Returns ``(A3, A4, A5, A6, A7, scene)`` — pure Python, no DLL executed.
    The blocks carry L's slots bit-exact; bytes outside L's dependency closure
    are left 0 (they feed no L slot).  ``scene`` is ``obj`` with the four header
    words written.
    """
    A6, counts = measure_bank_block(image, offsets, sel=sel, en=en,
                                    dll_path=dll_path)
    objb = bytearray(obj)
    selection_mask(image, offsets, sel=sel, mode=mode, mode_pack=mode_pack,
                   en=en, par=par, obj=objb, dll_path=dll_path)
    mask = bytes(objb[0xC20:0xC20 + N_SAMPLES])
    hdr = measure_whole_frame(A6, image, offsets, mask, sel=sel, en=en,
                              dll_path=dll_path)

    A7 = bytearray(_A7_LEN)
    for n in range(14):
        struct.pack_into("<H", A7, 2 * n, A7_BANK_DIVISORS[n] & 0xFFFF)
    struct.pack_into("<H", A7, 0x1C, hdr["n_mask1"] & 0xFFFF)
    struct.pack_into("<H", A7, 0x1E, hdr["n_mask1"] & 0xFFFF)
    struct.pack_into("<H", A7, 0x20, hdr["n_m1_b4"] & 0xFFFF)
    struct.pack_into("<H", A7, 0x22, hdr["n_m1_b4"] & 0xFFFF)

    hd = build_histograms(image, offsets, mask, sel=sel, dll_path=dll_path)
    A3 = bytearray(_A3_LEN)
    A4 = bytearray(_A4_LEN)
    A5 = bytearray(_A5_LEN)
    for entry, (hid, k) in _A3_PERCENTILES.items():
        struct.pack_into("<i", A3, 4 * entry, _i32(_percentile(hd[hid], k)))
    for entry, hid in _A4_MEAN_GE2.items():
        struct.pack_into("<i", A4, 4 * entry, _i32(_mean_ge2(hd[hid])))
    for entry, hid in _A5_MODE.items():
        struct.pack_into("<i", A5, 4 * entry, _i32(_mode(hd[hid])))

    scene = bytearray(obj)
    struct.pack_into("<H", scene, 0x06, hdr["n_mask1"] & 0xFFFF)
    struct.pack_into("<H", scene, 0x08, hdr["sum_sel_m1"] & 0xFFFF)
    struct.pack_into("<H", scene, 0x0A, hdr["n_m1_b4"] & 0xFFFF)
    struct.pack_into("<H", scene, 0x0C, hdr["sum_sel_m1_b4"] & 0xFFFF)
    return bytes(A3), bytes(A4), bytes(A5), bytes(A6), bytes(A7), bytes(scene)


def l_input_vector(*, image, offsets, sel, arg4, en, par, obj, mode, mode_pack,
                   dll_path=None):
    """Slots 0..719 of the pcode L-term's input vector (``obj+0x3c``).

    Runs the already-ported packer ``fcn.102b7440`` over the pure-Python
    A-blocks.  Every slot the L-term reads is bit-exact against the real vendor;
    slots outside L's closure are packed from the (zero) non-L block bytes and
    are not claimed.  The 720..732 tail is ``fcn.1028b8d0``'s own contribution
    (``pakon_orderfpo_vecpack.vecpack_tail``), outside this function.
    """
    import pakon_orderfpo_vecpack as _vp
    A3, A4, A5, A6, A7, scene = measure_l_blocks(
        image=image, offsets=offsets, sel=sel, en=en, par=par, obj=obj,
        mode=mode, mode_pack=mode_pack, dll_path=dll_path)
    S, _, _ = _vp.vecpack(bytearray(scene), mode=mode_pack, arg2=arg4,
                          arg3=A3, arg4=A4, arg5=A5, arg6=bytearray(A6),
                          arg7=bytearray(A7), arg8=bytes(en), arg9=bytes(par))
    return _vp.read_vector(S)


# ---------------------------------------------------------------------------
# The measure INPUT-PREP (frame -> image/offsets/arg0), derivation half.
#
# fcn.1028b8d0 (sba_order_fpo_calc, the caller of fcn.102aece0) consumes three
# per-frame inputs the SBA balance A is computed from:
#
#   * ``image``   = the 24x36x6 int16 sample grid (measure arg0 == the caller's
#                   own arg_2d4h, passed in already filled);
#   * ``offsets`` = the six int32 band-subtraction constants (measure arg1 ==
#                   caller ``&var_1ch``, which the caller BUILDS from an RGB
#                   opening triple at ``0x1028b96b..0x1028ba28``);
#   * ``arg0``    = the opponent Y/C1/C2 density block ``compute_uv`` reads at
#                   ``0x1440/0x1B00/0x21C0``.
#
# Three facts, each verified BIT-EXACT (tier 2) against the closecolor live
# capture (6/6 frames, `/tmp/pakon_re/wire2/prove_derivation.py`):
#
#   1. ``offsets`` is ROLL-CONSTANT and equals
#          [R0,G0,B0] + fos_opening_axes(R0,G0,B0)
#      where (R0,G0,B0) is the roll opening RGB (arg5[0:6]).  On the captured
#      roll that is (879,1250,1386,2029,96,359) for every frame.  The caller's
#      own magic-divide arithmetic at 0x1028b979.. IS ``fos_opening_axes`` (same
#      BIAS_Y/C1/C2, MAGIC_Y/C1/C2, sar).
#   2. Sample bands 3/4/5 are ``fos_opening_axes`` applied PER SAMPLE to bands
#      0/1/2 (864/864 samples, 6/6 frames).
#   3. ``arg0[0:0x2880]`` IS the six-band sample grid, same layout as ``image``
#      (band k at byte 0x6C0*k).  ``compute_uv`` reads only bands 3/4/5, so an
#      ``arg0`` rebuilt from bands 0-2 gives an identical U/V and an identical A.
#
# Consequence: the entire prep reduces to ONE genuinely-upstream unknown -- the
# 24x36x3 RGB density grid (bands 0-2) -- and this function derives everything
# else from it.  See NOT_PORTED note below: producing bands 0-2 from the frame
# (the frame->grid sampler) is NOT ported/validated here.
# ---------------------------------------------------------------------------

#: byte offset of each of the six sample bands inside ``arg0`` (== inside the
#: measure sample grid), cite arg0 layout probe 0x0/0x6C0/0xD80/0x1440/0x1B00/
#: 0x21C0.  ``compute_uv`` reads bands 3/4/5 (OFF_Y/OFF_C1/OFF_C2).
ARG0_BAND_STRIDE = 0x6C0                  # 864 int16
ARG0_LEN = 0x3000                         # captured arg0 allocation (12288 B)

#: NOT reproduced here: the frame -> (bands 0-2) sampler.  It is performed
#: upstream of fcn.1028b8d0 (which receives the grid already filled as its
#: arg_2d4h), by a function reached through an INDIRECT call (no immediate xref
#: to 0x1028b8d0 exists in PakonIMAu.dll -- return-address swap), and it samples
#: the per-frame "area image" (245x367x3 12-bit, the area_image_apply_lut
#: output) -- which the live capture dumps only TRUNCATED (0x80000 of the
#: 0x83B62 needed) and which is not a simple decimation of.  Bands 0-2 must
#: therefore be supplied by the caller; this function does not invent them.
MEASURE_PREP_SAMPLER_PORTED = False


def build_measure_inputs(rgb_bands, opening_rgb):
    """Derive ``(image, offsets, arg0)`` from the 24x36 RGB density grid.

    ``rgb_bands`` -- the three sample bands 0/1/2 (R,G,B density), each a
    length-864 sequence of ints in plane-major order (row stride 36); a
    ``(3,864)`` / ``(3,24,36)`` / ``(24,36,3)`` array is accepted and flattened.
    ``opening_rgb`` -- the roll opening triple ``(R0,G0,B0)`` (arg5[0:6]).

    Returns:
      * ``image``   -- list of 5184 int16 (6 bands, plane-major), == the vendor
                       ``measure_samples`` GIVEN correct bands 0-2;
      * ``offsets`` -- list of six int32, == the vendor ``measure_bandsub``;
      * ``arg0``    -- ``bytes`` of length ``ARG0_LEN``; its bands 3/4/5 (the
                       only region ``compute_uv`` reads) are exact.

    Bit-exact (tier 2, 6/6 live frames) for the DERIVATION; the correctness of
    bands 0-2 is the caller's responsibility (see ``MEASURE_PREP_SAMPLER_PORTED``
    -- the frame->grid sampler is unported).
    """
    from pakon_fos import fos_opening_axes

    b0, b1, b2 = _normalize_rgb_bands(rgb_bands)
    b3 = [0] * N_SAMPLES
    b4 = [0] * N_SAMPLES
    b5 = [0] * N_SAMPLES
    for i in range(N_SAMPLES):
        y, c1, c2 = fos_opening_axes(b0[i], b1[i], b2[i])
        b3[i], b4[i], b5[i] = y, c1, c2
    image = list(b0) + list(b1) + list(b2) + b3 + b4 + b5

    R0, G0, B0 = (int(v) for v in opening_rgb)
    offsets = [R0, G0, B0, *fos_opening_axes(R0, G0, B0)]

    arg0 = bytearray(ARG0_LEN)
    struct.pack_into("<%dh" % (6 * N_SAMPLES), arg0, 0,
                     *[_i16(v) for v in image])
    return image, offsets, bytes(arg0)


def _normalize_rgb_bands(rgb_bands):
    """Coerce ``rgb_bands`` into three length-864 plane-major int lists."""
    try:
        import numpy as _np
    except Exception:  # pragma: no cover - numpy always present in-tree
        _np = None
    if _np is not None and isinstance(rgb_bands, _np.ndarray):
        a = rgb_bands
        if a.shape == (3, N_SAMPLES):
            planes = a
        elif a.shape == (3, N_ROWS, N_COLS):
            planes = a.reshape(3, N_SAMPLES)
        elif a.shape == (N_ROWS, N_COLS, 3):
            planes = a.transpose(2, 0, 1).reshape(3, N_SAMPLES)
        else:
            raise ValueError("rgb_bands array must be (3,864)/(3,24,36)/(24,36,3)")
        return [[int(v) for v in planes[k]] for k in range(3)]
    bands = [list(b) for b in rgb_bands]
    if len(bands) != 3:
        raise ValueError("rgb_bands must be three bands (R,G,B)")
    out = []
    for b in bands:
        if len(b) == N_SAMPLES:
            out.append([int(v) for v in b])
        elif len(b) == N_ROWS and all(len(r) == N_COLS for r in b):
            out.append([int(v) for r in b for v in r])
        else:
            raise ValueError("each band must be 864 samples (or 24x36)")
    return out
