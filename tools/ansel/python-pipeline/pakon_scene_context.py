#!/usr/bin/env python3
"""AnsSceneContext find/insert — dmin bag for CnPremium mid-aims.

PakonIMAu.dll base ``0x10000000``. Host models the named property bag that
``CnPremium_analyzeSceneSpecific`` reads for mid-aim RGB. Do **not** invent
scene dmin values — only pack/unpack + bag I/O matching the binary.

VERIFIED
========

``AnsSceneContext::find`` @ ``0x10022a40``
-----------------------------------------
* String ``0x10576ba4`` / source ``AnsSceneContext.cpp`` ``0x10576bd4``.
* Looks up name in map at ``this+0xc`` via ``0x10022900``; on hit copies
  stored blob into caller buffer (``rep movsd`` @ ``0x10022bc4``).
* CnPremium mid-aim call @ ``0x100566ac``:

  - Seed stack RGB ``[ebp-0x34…]`` from ShastaParams ``black`` (``+0x3c``)
    replicated to R=G=B (``0x10056663…``).
  - ``find("dmin" @ ``0x105737c8``, size=6, buf=*)`` — 6-byte RGB int16.
  - Success (status == null sentinel ``0x106b5bd4``) continues to
    ``NoiseMethods::getNoiseTable`` @ ``0x10112980``; failure aborts
    SceneSpecific (no silent keep-seed on the dens path).

``AnsSceneContext::insert`` @ ``0x10023f10``
-------------------------------------------
* String ``0x10576c98``.
* Args include name, data pointer, byte size, overwrite flag.

Cited dmin **writers** (size=6, name ``"dmin"``):

1. ``CiColorCorrectionAnsel::bAddScene`` @ insert site ``0x10002523``
   (string ``0x10573a58``). Jump table ``0x10002824`` on desc
   ``+0x48`` (``cmp eax,4; ja``):

   | case | entry        | packs dmin from desc? | ``ebp-0x18`` |
   |------|--------------|-----------------------|--------------|
   | 0    | ``0x10002318`` | no                    | 3            |
   | 1–3  | ``0x100022e6`` | **yes** ``+0x54/58/5c`` → ``ebp-0x38`` | 1 |
   | 4    | ``0x1000230b`` | no                    | 3            |

   Insert runs only when ``[ebp-0x18]==1`` (``0x100024f3``) — i.e. cases
   1–3. Pack leaf Unicorn-golden → ``BADDSCENE_DMIN_PACK_PORTED``.
2. ``ColorNegativePath::analyzeScpLutBalance`` @ ``0x100fdaa8``:
   - Remap ``path+0x3c/+0x3e/+0x40`` through a LUT (``0x100fd984…``),
   - ``lea esi, [edi+0x3c]`` then ``insert("dmin", esi, 6, …)``.

Host ``PIAnselAddScene`` / TLA desc pack (VERIFIED + Unicorn)
-----------------------------------------------------------
* Export ``PIAnselAddScene`` @ ``0x100183c0`` — thin wrapper:
  ``push arg3,arg2,arg1; ecx=singleton 0x106b5b18; call bAddScene``.
* TLA ``bKcdfsCorrections`` @ ``0x1003f720`` call site ``0x1003fb7a``:
  ``call [JT+0x54]`` with desc ``&esp+0x68``.
* Desc pack leaf ``0x1003f901…0x1003f941`` (Unicorn):

  1. ``rep stosd`` zero ``0x1a`` dwords (``0x68`` bytes) at desc.
  2. ``desc+0x48`` ← case dword (film-type switch → ``esp+0x14``).
  3. ``desc+0x54/+0x58/+0x5c`` ← dword stores of zero-extended words
     from locals ``esp+0x34/+0x3c/+0x44`` (bAddScene reads as int16).

* Seed RGB words before pack (``0x1003f7db…``): frame object
  ``+0x6cac/+0x6cb0/+0x6cb4`` → locals ``esp+0x34/+0x3c/+0x44``.
* Film-class ``vt+0x34``; ``test al,2`` @ ``0x1003f820`` selects
  ColRev ``JT+0x4c`` (``0x1003f82d…``) else ColNeg ``JT+0x44``
  (``0x1003f848…``). Call shape: planar ``width=4``, ``height=1``,
  in-place buffer with R/G/B at ``+0/+8/+16`` (pixel0 only seeded;
  MMX chunk width). ColNeg 1px = stage-2 LUT+matrix
  (``pakon_color.render_pixel`` / TLA ``0x1001c470``). ColRev still
  runs extra ``ColRevLut*`` stages after the shared kernel — host
  ports ColNeg remap only; ColRev dispatch bit is cited.
* Case table from ``[ebx]+0x34`` film class (``0x1003f89b…``).

``ADDSCENE_DESC_PACK_PORTED = True``.
``FRAME_DMIN_RGB_PORTED = True`` (FindDmin ``0x10009250`` hist leaf).
``ADDSCENE_COLNEG_REMAP_PORTED = True`` (TLA 1px ColNeg ``JT+0x44``).
``ADDSCENE_COLNEG_REMAP_F135_PORTED = True`` (TLB ``fcn.1000d880`` @
``0x10034b9b`` — roll prime before AddScene; docs/58 §7).

Frame ``+0x6cac`` producer — ``FN_bFindDmin`` / ``0x10009250`` (VERIFIED)
-----------------------------------------------------------------------
TLA ``fcn.10009250`` (caller ``0x10030d72``; log string ``FN_bFindDmin``):

* Per channel, hist of ROI samples into ``0x4000`` int32 bins, then
  high-side walk ``0x100093f0…0x1000941f`` (Unicorn-golden):

  - ``thr = (n_pixels * 0x10624dd3) >> 38`` ≡ ``n_pixels // 1000``
  - walk ``code`` from ``0x3fff`` down; ``cum += hist[code]`` until
    ``cum > thr``; if result still ``0x3fff`` store ``0``.
  - store dword at frame ``+0x6cac/+0x6cb0/+0x6cb4`` (``esi`` steps +4).

* ROI margins use frame ``+0xc6c/+0xc70`` and vtable getters
  (``+0x10/+0x20/+0x24/+0x44``); host API takes explicit per-channel
  samples (same leaf once the window is chosen).

``path+0x3c`` source — ``getCnContext`` (VERIFIED)
-------------------------------------------------
``ColorNegativePath::getCnContext`` @ ``0x100f8620`` (OrderWide):

* ``lea edi, [path+0x3c]``; ``find("dmin", size=6, buf=&path+0x3c)``
  @ ``0x100f8bd6…`` — find ``rep movsd`` fills the three int16s.
* On empty size (``0x100f8c6f…``): zero ``+0x3c/+0x3e/+0x40``.

No non-zero static ``mov word [path+0x3c]`` in cnMethods — the bag
copy **is** the source writer. FUGC Cap analyze still only *reads*
``&path+0x3c``. ``PATH_DMIN_FROM_BAG_PORTED = True``.

ScpLut remap @ ``0x100fd984…0x100fd9b3`` (VERIFIED + Unicorn)
-------------------------------------------------------------
Cap getter ``0x10122150`` → Impl ``0x10212100`` (``ret 0xc``) writes:

* ``out0`` ← ``int16`` at CapImpl ``+0x10`` blob ``+0`` → **stride**
* ``out1`` ← ``int16`` at blob ``+2`` (unused by remap)
* ``out2`` ← ``dword`` at blob ``+4`` → **int16 LUT** base

Call-site push order aliases ``stride`` to ``[esp+0x2c]`` and LUT to
``[esp+0x20]``. Remap (in place on ``path+0x3c``):

* ``R' = lut[R]``
* ``G' = lut[G + stride]``
* ``B' = lut[B + 2·stride]``

``SCPLUT_DMIN_REMAP_PORTED = True``.

Other ``"dmin"`` push sites exist (FUGC / noise / …); mid-aim **reader**
is the CnPremium ``find`` above.

Host bag
--------
``SceneContextBag`` is a plain name→bytes map. It is **not** a COM port of
``0x10022a40`` / ``0x10023f10`` (STL/refcount). It is enough to feed
``cn_premium_mid_aim_rgb`` when the host already knows dmin RGB (e.g. from
bAddScene desc or ScpLut-remapped ``path+0x3c``).

``SCENE_CONTEXT_DMIN_PORTED = True`` — bag I/O + pack/unpack + ScpLut
remap + bAddScene pack + AddScene desc pack + getCnContext path load +
FindDmin ``+0x6cac`` leaf + ColNeg 1px remap. AneOrder build orch
``0x1027e9d0`` is ported too (``pakon_ane_order.ANE_ORDER_PORTED``), which is
what ``pakon_shasta.SHASTA_ANALYZE_PORTED = True`` records.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Sequence

SCENE_CONTEXT_DMIN_PORTED = True
SCPLUT_DMIN_REMAP_PORTED = True
BADDSCENE_DMIN_PACK_PORTED = True
ADDSCENE_DESC_PACK_PORTED = True
PATH_DMIN_FROM_BAG_PORTED = True
FRAME_DMIN_RGB_PORTED = True
ADDSCENE_COLNEG_REMAP_PORTED = True
# TLB.dll @ 0x10034b9b — ColNeg dmin prime via fcn.1000d880 (not JT+0x44)
ADDSCENE_COLNEG_REMAP_F135_PORTED = True

SCENE_CONTEXT_FIND = 0x10022A40
SCENE_CONTEXT_INSERT = 0x10023F10
STR_DMIN = 0x105737C8
STR_FIND = 0x10576BA4
STR_INSERT = 0x10576C98
STR_BADDSCENE = 0x10573A58

CN_PREMIUM_DMIN_FIND_CALL = 0x100566AC  # E8 → find
BADDSCENE_DMIN_INSERT = 0x10002523
BADDSCENE_DMIN_PACK = 0x100022E6  # cases 1–3: desc → ebp-0x38
BADDSCENE_DMIN_PACK_END = 0x10002309  # before jmp join
BADDSCENE_CASE_JT = 0x10002824  # dword[5] jump table on desc+0x48
PIANSEL_ADD_SCENE = 0x100183C0  # export → bAddScene
BADDSCENE = 0x10002290
TLA_BKCDFS_CORRECTIONS = 0x1003F720  # TLA.dll
TLA_ADDSCENE_CALL = 0x1003FB7A  # call [JT+0x54]
TLA_DESC_PACK = 0x1003F901  # zero + case + RGB dword stores
TLA_DESC_PACK_END = 0x1003F941  # before call [vt+0x70]
TLA_FRAME_DMIN_R_OFF = 0x6CAC
TLA_FRAME_DMIN_G_OFF = 0x6CB0
TLA_FRAME_DMIN_B_OFF = 0x6CB4
TLA_FIND_DMIN = 0x10009250  # FN_bFindDmin body (TLA.dll)
TLA_FIND_DMIN_HIST_WALK = 0x100093F0  # high-side cum walk → store
TLA_FIND_DMIN_HIST_WALK_END = 0x10009422  # after dword store
TLA_FIND_DMIN_THR_MAGIC = 0x10624DD3  # (n * magic) >> 38 == n // 1000
TLA_FIND_DMIN_N_BINS = 0x4000  # 14-bit hist
TLA_FIND_DMIN_CODE_MAX = 0x3FFF
TLA_ADDSCENE_SEED_FRAME = 0x1003F7DB  # mov dx,[ebx+0x6cac]…
TLA_ADDSCENE_COLNEG_CALL = 0x1003F85E  # call [JT+0x44]
TLA_ADDSCENE_COLREV_CALL = 0x1003F843  # call [JT+0x4c]
TLA_ADDSCENE_FILM_BIT2 = 0x1003F820  # test al,2 → ColRev else ColNeg
# TLB.dll roll driver: prime ColNeg dmin through poly before AddScene
TLB_ADDSCENE_POLY_PRIME = 0x10034B9B  # call fcn.1000d880
TLB_COLOR_CORRECT_POLY = 0x1000D880
GET_CN_CONTEXT = 0x100F8620
GET_CN_CONTEXT_DMIN_FIND = 0x100F8BD6  # lea path+0x3c; find dmin
GET_CN_CONTEXT_DMIN_ZERO = 0x100F8C6F  # empty → zero +0x3c/3e/40
SCPLUT_DMIN_INSERT = 0x100FDAA8
SCPLUT_DMIN_REMAP = 0x100FD984  # path+0x3c through LUT, then insert
SCPLUT_CAP_GET_LUT = 0x10122150
SCPLUT_IMPL_GET_LUT = 0x10212100
PATH_DMIN_RGB_OFF = 0x3C  # 3×int16 at +0x3c/+0x3e/+0x40
DESC_BYTES = 0x68  # TLA zero span (0x1a dwords)
DESC_DMIN_CASE_OFF = 0x48
DESC_DMIN_R_OFF = 0x54
DESC_DMIN_G_OFF = 0x58
DESC_DMIN_B_OFF = 0x5C
DMIN_BYTES = 6
# Stage-2 ColNeg constants (TLA MMX kernel / pakon_color). Only
# _COLNEG_LUT_SIZE is arithmetic here — the rest are cited kernel facts kept
# for the record; the arithmetic itself is pakon_color.render_pixel_f235's.
_COLNEG_LUT_SIZE = 16384  # and 0x3fff @ 0x1001c57e — index FOLDS, not clamps
_COLNEG_COEFF_FIXED = 8192  # buildContext scale, TLA 0x10012eb0
_COLNEG_RPD_MAX = 4092  # paddw 0x8000 / paddusw 0x7003 / psubusw 0xf003
_COLNEG_PLANAR_WIDTH = 4  # MMX chunk; only pixel0 seeded from frame dmin
# width 4 → (width & 3) == 0 @ 0x1001c763, so the x87 scalar tail at
# 0x1001c785 runs ZERO times and MMX rounding is the whole answer.
COLNEG_PLANAR_WIDTH = _COLNEG_PLANAR_WIDTH  # public alias for the goldens
COLNEG_PLANAR_SCAN_EXPORT = 0x100064D0  # PIColorCorrectColNegPlanarScan
COLNEG_PLANAR_KERNEL = 0x1001C470  # MMX body it tail-calls
COLNEG_PLANAR_SCALAR_TAIL = 0x1001C785  # x87 (width mod 4) tail — not taken


def pack_dmin_rgb(r: int, g: int, b: int) -> bytes:
    """6-byte little-endian int16 RGB (find/insert size)."""
    return struct.pack("<hhh", int(r), int(g), int(b))


def unpack_dmin_rgb(blob: bytes) -> tuple[int, int, int]:
    """Inverse of ``pack_dmin_rgb``; requires exactly 6 bytes."""
    if len(blob) != DMIN_BYTES:
        raise ValueError(f"dmin blob must be {DMIN_BYTES} bytes, got {len(blob)}")
    r, g, b = struct.unpack("<hhh", blob)
    return int(r), int(g), int(b)


def baddscene_case_packs_dmin(case: int) -> bool:
    """True when desc ``+0x48`` selects packed dmin insert (cases 1–3)."""
    return int(case) in (1, 2, 3)


def baddscene_pack_dmin_from_desc(
    word_54: int, word_58: int, word_5c: int
) -> bytes:
    """bAddScene packed case @ ``0x100022e6…`` — desc ``+0x54/+0x58/+0x5c``.

    Unicorn-golden word copy into the 6-byte insert buffer (``ebp-0x38``).
    """
    return pack_dmin_rgb(word_54, word_58, word_5c)


def addscene_pack_desc(case: int, r: int, g: int, b: int) -> bytearray:
    """TLA AddScene desc pack @ ``0x1003f901…`` (Unicorn-golden).

    Zero ``DESC_BYTES``, store case at ``+0x48``, RGB as zero-extended
    dwords at ``+0x54/+0x58/+0x5c`` (bAddScene reads the low int16s).
    """
    desc = bytearray(DESC_BYTES)
    struct.pack_into("<I", desc, DESC_DMIN_CASE_OFF, int(case) & 0xFFFFFFFF)
    struct.pack_into("<I", desc, DESC_DMIN_R_OFF, int(r) & 0xFFFF)
    struct.pack_into("<I", desc, DESC_DMIN_G_OFF, int(g) & 0xFFFF)
    struct.pack_into("<I", desc, DESC_DMIN_B_OFF, int(b) & 0xFFFF)
    return desc


def addscene_desc_dmin_rgb(desc: bytes | bytearray) -> tuple[int, int, int]:
    """Read desc ``+0x54/+0x58/+0x5c`` as int16 (bAddScene view).

    TLA stores zero-extended **dwords** at those offsets; bAddScene
    reads the low int16 of each (not three packed consecutive words).
    """
    if len(desc) < DESC_DMIN_B_OFF + 4:
        raise ValueError("desc too short for dmin dwords")
    r = struct.unpack_from("<h", desc, DESC_DMIN_R_OFF)[0]
    g = struct.unpack_from("<h", desc, DESC_DMIN_G_OFF)[0]
    b = struct.unpack_from("<h", desc, DESC_DMIN_B_OFF)[0]
    return int(r), int(g), int(b)


def getcncontext_path_dmin_from_bag(
    bag: "SceneContextBag",
) -> tuple[int, int, int]:
    """getCnContext path ``+0x3c`` load @ ``0x100f8bd6…`` / zero ``0x100f8c6f``.

    Host stand-in for ``find("dmin", size=6, buf=&path+0x3c)``: return
    bag RGB, or ``(0,0,0)`` when absent (DLL zeroes the three words).
    """
    rgb = bag.find_dmin()
    if rgb is None:
        return (0, 0, 0)
    return rgb


def scplut_remap_dmin_rgb(
    lut: Sequence[int],
    stride: int,
    r: int,
    g: int,
    b: int,
) -> tuple[int, int, int]:
    """ScpLutBalance dmin remap @ ``0x100fd984…`` before insert.

    ``lut`` is int16-indexed (host may pass a list/array of int). Indices
    are ``R``, ``G+stride``, ``B+2*stride`` — cite Cap getter outs.
    """
    rr = int(r)
    gg = int(g)
    bb = int(b)
    s = int(stride)
    return int(lut[rr]), int(lut[gg + s]), int(lut[bb + 2 * s])


def scplut_remap_and_pack(
    lut: Sequence[int],
    stride: int,
    r: int,
    g: int,
    b: int,
) -> bytes:
    """Remap then pack 6-byte dmin (insert payload)."""
    return pack_dmin_rgb(*scplut_remap_dmin_rgb(lut, stride, r, g, b))


def find_dmin_thr_n_pixels(n_pixels: int) -> int:
    """FindDmin threshold ``(n * 0x10624dd3) >> 38`` @ ``0x10009362…``.

    Equals ``n_pixels // 1000`` for non-negative ``n`` (Unicorn-checked).
    """
    return (int(n_pixels) * TLA_FIND_DMIN_THR_MAGIC) >> 38


def find_dmin_code_from_hist(
    counts: Sequence[int],
    thr: int,
    *,
    n_bins: int = TLA_FIND_DMIN_N_BINS,
) -> int:
    """High-side hist walk ``0x100093f0…0x1000941f`` (Unicorn-golden).

    Walk ``code`` from ``n_bins-1`` down; stop when cumulative count
    ``> thr``. If the first bin (``0x3fff``) already exceeds ``thr``,
    store ``0`` (DLL ``sete`` / ``and`` special case).
    """
    n = int(n_bins)
    if n <= 0:
        return 0
    code = n - 1
    cum = 0
    thr_i = int(thr)
    while True:
        if 0 <= code < len(counts):
            cum += int(counts[code])
        if thr_i < cum:
            break
        code -= 1
        if code == 0:
            break
    if code == n - 1:
        return 0
    return int(code)


def find_dmin_code_from_samples(
    samples: Sequence[int],
    *,
    n_bins: int = TLA_FIND_DMIN_N_BINS,
    thr: int | None = None,
) -> int:
    """Build 14-bit hist from samples then ``find_dmin_code_from_hist``.

    ``thr`` defaults to ``len(samples) // 1000`` via the magic mul.
    Sample values are masked to ``n_bins-1`` (DLL ``movzx`` path).
    """
    n = int(n_bins)
    hist = [0] * n
    n_pix = 0
    mask = n - 1
    for v in samples:
        hist[int(v) & mask] += 1
        n_pix += 1
    if thr is None:
        thr = find_dmin_thr_n_pixels(n_pix)
    return find_dmin_code_from_hist(hist, int(thr), n_bins=n)


def frame_dmin_rgb_from_planes(
    plane_r: Sequence[int],
    plane_g: Sequence[int],
    plane_b: Sequence[int],
    *,
    n_bins: int = TLA_FIND_DMIN_N_BINS,
) -> tuple[int, int, int]:
    """FindDmin → frame ``+0x6cac/+0x6cb0/+0x6cb4`` from per-channel samples.

    Caller supplies the ROI window (DLL margins via ``+0xc6c/+0xc70`` /
    vtable getters). Each plane is hist'd independently with
    ``thr = n_samples // 1000``.
    """
    return (
        find_dmin_code_from_samples(plane_r, n_bins=n_bins),
        find_dmin_code_from_samples(plane_g, n_bins=n_bins),
        find_dmin_code_from_samples(plane_b, n_bins=n_bins),
    )


def addscene_seed_from_frame_dmin(
    r: int, g: int, b: int
) -> tuple[int, int, int]:
    """TLA seed ``0x1003f7db…``: frame dmin words → pack locals (low 16)."""
    return int(r) & 0xFFFF, int(g) & 0xFFFF, int(b) & 0xFFFF


def addscene_film_uses_colrev(film_flags: int) -> bool:
    """``test al,2`` @ ``0x1003f820`` — bit1 set → ColRev ``JT+0x4c``."""
    return (int(film_flags) & 2) != 0


def addscene_colneg_remap_dmin_rgb(
    r: int,
    g: int,
    b: int,
    lut: Sequence[float] | Sequence[int],
    coeff: Sequence[Sequence[int]],
    offset: Sequence[int],
) -> tuple[int, int, int]:
    """1px ColNeg remap of frame dmin words — TLA ``JT+0x44`` path.

    DLL builds a planar ``width=4`` / ``height=1`` buffer with only pixel0
    of each plane set (``+0/+8/+16``), then runs
    ``PIColorCorrectColNegPlanarScan``. Host applies the verified stage-2
    closed form (LUT → 3×4 → clamp ``0…4092``) to that single pixel —
    same arithmetic as ``pakon_color.render_pixel_f235`` / TLA ``0x1001c470``.

    **This used to be re-derived here as a float closed form, and that was
    a real off-by-one bug** — the one `pakon_shasta_aim_golden.py`'s
    ``colneg_1px remap TLA`` case flagged as a "known failure" for six
    passes. The old body summed all three products and divided ONCE::

        acc = Σ_c coeff[k][c] * dens[c] / 8192 ; v = int(acc / 8 + offset[k])

    The kernel does not do that. ``0x1001c684…0x1001c68a`` is three
    separate ``pmulhw``, i.e. each product is independently truncated to
    its signed high word — ``floor(coeff*dens / 65536)`` — and only then
    are the three floors added with ``paddsw``. Σ floor(x_c) ≤ floor(Σ x_c),
    so the "sum first, divide once" form is systematically HIGH, by exactly
    one code whenever the discarded fractions of the three products carry.
    ``pakon_color.render_pixel_f235``'s own docstring already warned this is
    a different function (docs/58 §14.4); this function claimed to match it
    and then did the other thing. Delegate instead of re-deriving.

    Verified against the real DLL, not against the other host port: the
    TLA call site pushes ``width=4`` (``push 4`` @ ``0x1003f840``/
    ``0x1003f85d``), and ``0x1001c4cc`` (``shr ecx,2``) plus ``0x1001c763``
    (``and edx, 0x80000003`` → ``je`` past the tail) mean a width of 4 is
    handled entirely by the MMX block with ZERO iterations of the x87
    scalar tail at ``0x1001c785``. So the MMX rounding *is* the vendor
    answer here; the tail's different 1-LSB rounding never runs. Driving
    the real ``PIColorCorrectColNegPlanarScan`` (``0x100064d0``) under
    Unicorn on the TLA buffer shape agrees with ``render_pixel_f235``
    bit-exactly and disagrees with the old body on 5 of 7 probes.

    ColRev (``JT+0x4c``) shares this kernel then applies extra
    ``ColRevLut*`` stages — **not** included here; use
    ``addscene_film_uses_colrev`` for dispatch only.

    F-135 / TLB does **not** use this leaf for roll prime — see
    ``addscene_colneg_remap_dmin_rgb_f135`` (``TLB.dll @ 0x10034b9b``).
    """
    import os
    import sys

    _tools = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    if _tools not in sys.path:
        sys.path.insert(0, _tools)
    import pakon_color as pc  # noqa: E402

    raw = (
        int(r) & (_COLNEG_LUT_SIZE - 1),
        int(g) & (_COLNEG_LUT_SIZE - 1),
        int(b) & (_COLNEG_LUT_SIZE - 1),
    )
    # TLA 0x1001c470: pmulhw x3 → paddsw → paddsw offset → paddw 0x8000 /
    # paddusw 0x7003 / psubusw 0xf003 (clamp 0…_COLNEG_RPD_MAX).
    return pc.render_pixel_f235(raw, lut, coeff, offset)


def addscene_colneg_remap_dmin_rgb_f135(
    r: int,
    g: int,
    b: int,
    coeffs: Sequence[float] | None = None,
) -> tuple[int, int, int]:
    """F-135 ColNeg dmin prime — ``TLB.dll:fcn.1000d880`` @ ``0x10034b9b``.

    Roll driver ``fcn.10034a60`` calls poly on the seeded frame dmin words
    (``+0x6cac…``) before packing the AddScene desc (docs/58 §7). Not the
    TLA dens-LUT MMX leaf. Host closed form is ``pakon_color.poly_pixel``.
    """
    import os
    import sys

    _tools = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    if _tools not in sys.path:
        sys.path.insert(0, _tools)
    import pakon_color as pc  # noqa: E402

    c = list(coeffs) if coeffs is not None else pc.load_unit_matrix()
    # TLB.dll @ 0x10034b9b → fcn.1000d880
    return pc.poly_pixel((int(r), int(g), int(b)), c)


def addscene_dmin_rgb_from_frame(
    frame_r: int,
    frame_g: int,
    frame_b: int,
    *,
    film_flags: int = 0,
    model: str = "f135",
    coeffs: Sequence[float] | None = None,
    lut: Sequence[float] | Sequence[int] | None = None,
    coeff: Sequence[Sequence[int]] | None = None,
    offset: Sequence[int] | None = None,
) -> tuple[int, int, int]:
    """Seed from frame ``+0x6cac`` RGB, optionally ColNeg-remap for desc pack.

    ``model='f135'`` (default): TLB poly prime ``0x10034b9b``.
    ``model='f235'``: TLA dens LUT+3×4 when ``lut``/``coeff``/``offset`` given.
    ColRev bit returns the seeded words unchanged (extra ColRev stages not
    host-ported).
    """
    seeded = addscene_seed_from_frame_dmin(frame_r, frame_g, frame_b)
    if addscene_film_uses_colrev(film_flags):
        return seeded
    if model == "f135":
        if not ADDSCENE_COLNEG_REMAP_F135_PORTED:
            return seeded
        return addscene_colneg_remap_dmin_rgb_f135(*seeded, coeffs)
    if lut is None or coeff is None or offset is None:
        return seeded
    return addscene_colneg_remap_dmin_rgb(*seeded, lut, coeff, offset)


@dataclass
class SceneContextBag:
    """Host stand-in for AnsSceneContext named blobs (dmin and kin)."""

    items: dict[str, bytes] = field(default_factory=dict)

    def insert(self, name: str, data: bytes, *, overwrite: bool = True) -> None:
        """``0x10023f10`` contract: store ``data`` under ``name``."""
        if not overwrite and name in self.items:
            return
        self.items[name] = bytes(data)

    def insert_dmin(self, rgb: tuple[int, int, int] | list[int], *, overwrite: bool = True) -> None:
        self.insert("dmin", pack_dmin_rgb(rgb[0], rgb[1], rgb[2]), overwrite=overwrite)

    def find(self, name: str, size: int | None = None) -> bytes | None:
        """``0x10022a40`` contract: return blob or ``None`` if missing.

        When ``size`` is set, require exact length (CnPremium passes 6).
        """
        blob = self.items.get(name)
        if blob is None:
            return None
        if size is not None and len(blob) != size:
            raise ValueError(f"{name!r}: stored {len(blob)} bytes, find size={size}")
        return bytes(blob)

    def find_dmin(
        self,
        *,
        seed_black: int | None = None,
    ) -> tuple[int, int, int] | None:
        """CnPremium dmin read: optional black seed, then find size=6.

        Returns ``None`` if ``dmin`` is absent (DLL aborts SceneSpecific).
        When present, returns the stored RGB (seed is only the pre-find
        stack init the binary overwrites on success).
        """
        blob = self.find("dmin", DMIN_BYTES)
        if blob is None:
            return None
        return unpack_dmin_rgb(blob)


def main() -> None:
    print("AnsSceneContext dmin bag (base 0x10000000)")
    print(f"  find   {SCENE_CONTEXT_FIND:#010x}")
    print(f"  insert {SCENE_CONTEXT_INSERT:#010x}")
    print(f"  CnPremium find call {CN_PREMIUM_DMIN_FIND_CALL:#010x}")
    print(f"  bAddScene insert    {BADDSCENE_DMIN_INSERT:#010x}")
    print(f"  bAddScene pack      {BADDSCENE_DMIN_PACK:#010x}")
    print(f"  PIAnselAddScene     {PIANSEL_ADD_SCENE:#010x}")
    print(f"  TLA desc pack       {TLA_DESC_PACK:#010x} (TLA.dll)")
    print(f"  getCnContext        {GET_CN_CONTEXT:#010x}")
    print(f"  ScpLut insert       {SCPLUT_DMIN_INSERT:#010x} (remap {SCPLUT_DMIN_REMAP:#010x})")
    print(f"  ScpLut getLut Cap/Impl {SCPLUT_CAP_GET_LUT:#010x}/{SCPLUT_IMPL_GET_LUT:#010x}")
    bag = SceneContextBag()
    bag.insert_dmin((100, 200, 300))
    print(
        f"  roundtrip {bag.find_dmin()} "
        f"SCENE_CONTEXT_DMIN_PORTED={SCENE_CONTEXT_DMIN_PORTED} "
        f"BADDSCENE_PACK={BADDSCENE_DMIN_PACK_PORTED} "
        f"ADDSCENE_DESC={ADDSCENE_DESC_PACK_PORTED} "
        f"PATH_FROM_BAG={PATH_DMIN_FROM_BAG_PORTED} "
        f"FRAME_DMIN={FRAME_DMIN_RGB_PORTED} "
        f"COLNEG_REMAP={ADDSCENE_COLNEG_REMAP_PORTED} "
        f"COLNEG_REMAP_F135={ADDSCENE_COLNEG_REMAP_F135_PORTED}"
    )
    demo = frame_dmin_rgb_from_planes(
        [100, 100, 5000, 5000],
        [200, 200, 6000, 6000],
        [300, 300, 7000, 7000],
    )
    print(f"  find_dmin demo RGB={demo} thr4={find_dmin_thr_n_pixels(4)}")
    desc = addscene_pack_desc(2, 100, 200, 300)
    print(
        f"  addscene desc case={struct.unpack_from('<I', desc, DESC_DMIN_CASE_OFF)[0]} "
        f"rgb={addscene_desc_dmin_rgb(desc)}"
    )
    print(f"  getCnContext path dmin={getcncontext_path_dmin_from_bag(bag)}")
    lut = list(range(400))
    print(
        f"  scplut remap sample {scplut_remap_dmin_rgb(lut, 100, 5, 6, 7)} "
        f"REMAP_PORTED={SCPLUT_DMIN_REMAP_PORTED}"
    )
    print(
        f"  bAddScene cases pack? "
        f"{[baddscene_case_packs_dmin(c) for c in range(5)]}"
    )


if __name__ == "__main__":
    main()
