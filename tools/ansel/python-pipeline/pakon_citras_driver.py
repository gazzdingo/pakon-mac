#!/usr/bin/env python3
r"""``ImaCitrasOpBase::virtual_40`` -- the citras-apply PER-PIXEL DRIVER.

``PakonIMAu.dll`` VA ``0x10169350``..``0x10169d0a`` (2,490 B), vtable offset
``0x28`` on ``ImaCitrasOpBase``'s own table (``pakon_citras_apply.py``'s
``CITRAS_APPLY_SLOTS`` catalogued this slot as "inherited" for a long time; it
is not boilerplate -- it self-names live as ``.\ImaCitrasOpBase.cpp`` via five
error strings including ``"The CITRAS op can only produce entire images."``).

WHY THIS FILE IS SEPARATE FROM ``pakon_citras_apply.py``
=======================================================
``pakon_citras_apply.py`` is the Unicorn-verified LEAF file and is deliberately
stdlib-only (its ``CitrasPlane``/``ComposeOperand`` models are scalar, one
Python loop per pixel -- exactly right for bit-exact golden comparison against
a few hundred emulated pixels, and hopelessly slow for a 7.4-megapixel frame).
This file is the ORCHESTRATION the render path actually calls: the same
arithmetic, vectorised with numpy, plus the four intermediate image stages the
driver builds between the leaf calls. ``pakon_citras_driver_golden.py`` proves
the numpy forms agree with ``pakon_citras_apply.py``'s scalar, DLL-verified
originals element for element, so this file inherits their verification rather
than restating it.

THE MECHANISM, AS THE DRIVER ACTUALLY WIRES IT
==============================================
Eight prior passes (docs/66 "6.2 continued", passes 1-8) established the STAGE
LIST but never the operand wiring. The wiring below was recovered by
disassembling the whole 2,490-byte body with capstone and manually tracking
ESP through every ``push``/``call``/``ret N`` -- the same technique
``CITRAS_APPLY_AVOIDANCE_BLEND_PORTED``'s own comment records as necessary
here (r2's ``pdf`` and r2ghidra's ``pdg`` both mis-locate stack locals in this
function family). Let ``F`` be ESP immediately after the prologue
(``sub esp,0x2dc`` + four register pushes); then the driver's own two stack
arguments are ``[F+0x2fc]`` (arg0) and ``[F+0x300]`` (arg1).

Cross-check that the ESP tracking is right, not just plausible: every one of
the four dispatched callees' ``ret N`` matches the number of dwords this
reading says the driver pushes for it -- ``virtual_56`` ``ret 0xc`` (3),
``virtual_60`` ``ret 0x10`` (4), ``virtual_64`` ``ret 8`` (2), the gradient
fragment ``0x10168f30`` ``ret 8`` (2). Four independent agreements.

Notation: ``img`` is the 3-band I16 image the op operates on (arg0, the
output operand -- pre-filled from ``this->0x104`` by the ``fillRWBuffer``
call at ``0x1016954a``, then mutated in place); ``W``/``H`` are
``this->0x104``'s own ``+0x20``/``+0x24`` (read at ``0x101693df``).

    bs   = this->0x118                      # blockSize      (0x10169555)
    r    = trunc(sigma * 3.0)                # Gaussian radius (0x1016958f..a6)
    BW   = ceil(W/bs); BH = ceil(H/bs)        # 0x10169561..0x1016958b
    padW = BW*bs;      padH = BH*bs

    obj1 = new plane(W, H, i16)               # 0x101695f3
    obj2 = new plane(max(padW, BW+2r),         # 0x10169685 -- a SCRATCH plane,
                     max(padH, BH+2r), i16)     #   reused three times below
    virtual_64(this, img, obj1)                # 0x101696c6  lum = luminance(img)
    obj2.roi = {0,0,padW,padH}                  # 0x101696e8
    if (padW,padH) == (W,H):  P = obj1          # 0x10169715
    else:  P = borderExtend(obj1 -> obj2)        # 0x1016977c, P = obj2

    obj3 = new plane(BW, BH, i16)                 # 0x101697f1
    obj3 = blockAverage(P, factor=bs)              # ctor 0x10169842 + slot 0x28
                                                    #   at 0x10169861
    obj2.roi = {0,0,BW+2r,BH+2r}                    # 0x101698b5
    if r == 0:  E = obj3                             # 0x101698c7
    else:  E = mirrorExtend(obj3 -> obj2, margin=r)   # 0x10169922, E = obj2

    K    = gaussianKernel(sigma)                      # 0x1016994a -> 0x10168d90
    S    = gaussBlur(E, K, clamp=[minValue,maxValue])  # 0x101699d7 (slot 0x34)
    obj4 = new plane(BW, BH, u8)                        # 0x10169a60
    gradientWeight(this, S, obj4)                        # 0x10169a9f -> 0x10168f30

    obj2.roi = {0,0,padW,padH}                            # 0x10169ac1
    obj2 = upsample(S)                                     # 0x10169af7
    obj5 = new plane(padW, padH, u8)                        # 0x10169b3f
    obj5 = upsample(obj4)                                    # 0x10169b7d
    obj2.roi = {0,0,W,H}                                      # 0x10169ba6

    virtual_60(this, s=obj2, opA=obj5, opB=obj1, opC=obj2)     # 0x10169bf3
    virtual_56(this, base=obj2, correction=obj1, term=img)      # 0x10169c30

**``s`` and ``opC`` are the SAME object** (both ``obj2``) -- the avoidance
blend runs in place over the reference plane. That is not a transcription
slip: the driver copy-constructs ``[F+0x20]`` (which was assigned ``obj2`` at
``0x10169acf``) and ``[F+0x14]`` (``obj2`` since ``0x1016968e``) into two
different argument slots at ``0x10169bde`` and ``0x10169bb7``. Reading
``s[r][c]`` and then writing ``opC[r][c]`` in the same iteration makes
in-place safe, and ``pakon_citras_apply.apply_avoidance_blend`` already
happens to do exactly that ordering.

WHY THE OUTPUT IS A DELTA, AND WHY ``term + base`` THEN RECONSTRUCTS RGB
=======================================================================
``virtual_60`` bias-subtracts the shared tone table for the duration of its
own call (``table[i] -= i`` before the loop, ``+= i`` after -- already
Unicorn-verified in ``pakon_citras_apply.py``), so what it writes is
``toneLut[idx] - idx``: a per-pixel LUMINANCE DELTA, not a toned value. The
following ``virtual_56`` adds that 1-band delta to all three bands of the
real image (base's single band broadcasts, already Unicorn-verified) and
clamps. So the vendor's real apply is:

    out_rgb = clamp(rgb + (toneLut[idx] - idx),  minValue, maxValue)
    idx     = lum - trunc((weight*(lum - reference) + 50) / 100)

i.e. **process in luma, restore chroma** -- and the index the tone curve is
looked up at is pulled from the pixel's own luminance toward a heavily
smoothed reference by ``weight`` percent, which is exactly the
"gradient-avoidance" behaviour this capability is named for. With
``weight == 100`` (smooth regions) the curve is applied to the SMOOTHED
luminance; with ``weight == minAvoidance`` (near edges) it is applied much
closer to the pixel's own luminance.

This vindicates the SHAPE of the interim stand-in that used to live in
``pakon_ansel.real_auto_tone`` (tone the luminance, broadcast the delta to
R/G/B) while showing exactly what it was missing: the index is not the raw
per-pixel luminance, and the result is clamped to ``[minValue, maxValue]``
rather than scaled by a hand-tuned constant.

THE SHARED TONE TABLE (``this->0x108``)
=======================================
Traced this pass, closing docs/66's third-pass open question about how
``setToneLut``'s output reaches a pixel. ``AnsImaCitrasAggregate``'s ctor
(``0x100ad7f0``) reads the ``AnsCitrasOperand``'s ``+0x30``/``+0x34``
(``lutSize``/``ToneLut`` -- the exact two fields
``pakon_citras_apply.apply_set_tone_lut`` writes) at ``0x100ad971`` and
constructs ``Tsc1DLutT<short>(ToneLut, lutSize, 1)`` at ``0x100ad9b8``
(``0x10099a40``), whose base ctor ``0x102f4b10`` stores **count = lutSize**
at ``+0xc`` and **bias = 0** at ``+0x10``, and whose body copies ``lutSize``
words into a fresh array reached through the ``+0x18`` double indirection.
That object is what ``ImaI16CitrasOp``'s ctor installs at ``this->0x108``
(``0x100aea02``) and what ``virtual_60`` looks up.

So the table IS the analyzed tone LUT, indexed directly, with bias 0 and
``count == lutSize == 4096`` for CN-Enhanced. **One deliberate divergence**:
``virtual_60``'s index is a raw wrapped int16 and the DLL indexes the array
with it unchecked, so a luminance outside ``[0, lutSize-1]`` reads adjacent
heap -- genuine vendor UB, in the same family as ``pakon_dra``'s already
documented out-of-bounds histogram indexing. This port CLAMPS the index into
``[0, lutSize-1]`` instead (for both the lookup and the ``- idx`` bias term,
so the pair stays consistent), which is also what every other ``*Lut`` in
this chain already does. Flagged, not hidden.

PARAMETERS
==========
``ImaI16CitrasOp``'s ctor (``0x100ae9b0``) defaults ``this->0x110..0x128``
from the literal block at ``0x1058f4e8`` -- read directly out of ``.rdata``
this pass: ``sigma = 8.25``, ``blockSize = 8``, ``minAvoidance = 70``,
``maxGradient = 4095``, ``lowGradientThreshold = -1``,
``highGradientThreshold = -1``, ``minValue = 0``, ``maxValue = 4095``,
matching ``pakon_citras.CITRAS_PARAMS_LAYOUT``'s own defaults exactly. It
additionally hard-codes ``this->0x124`` (``bDoClipping``) to **1** at
``0x100aea5d`` (``mov byte ptr [edi+0x14], 1``, ``edi == this+0x110``) --
that field is NOT part of ``AnsCitrasParams`` and has no ``.dpi`` source, so
the clamp in ``virtual_56`` is unconditionally ON for this op.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# --- VAs, for grep-ability against the disassembly ------------------------
CITRAS_DRIVER = 0x10169350            # ImaCitrasOpBase::virtual_40
GAUSSIAN_KERNEL_FN = 0x10168D90       # builds the normalised 1-D kernel
GRADIENT_WEIGHT_FN = 0x10168F30       # builds the avoidance table + weights
BLOCK_AVERAGE_COMPUTE = 0x10154EA0    # ImaBlockAverageOp, vtable slot 0x28
SIGMA_TO_RADIUS_CONST = -3.0          # qword [0x10578478], read from .rdata
HIGH_THRESHOLD_CONST = 8057.2168125   # qword [0x1058de98]
LOW_THRESHOLD_SCALE = 0.1273          # qword [0x1057fbb0]
LOW_THRESHOLD_BIAS = 18.0             # qword [0x1057fba8]


# CITRAS_DRIVER_WIRING_PORTED -- the operand wiring of 0x10169350 itself:
# which buffer feeds which argument of virtual_64/virtual_60/virtual_56 and
# the gradient fragment, in what order, at what resolution. Recovered by full
# capstone disassembly with manual ESP tracking (see this module's docstring
# for the resulting stage list with a VA on every line) and cross-checked
# four independent ways against each callee's own `ret N`. This flag is about
# the WIRING; each leaf's own arithmetic carries its own flag, in
# pakon_citras_apply.py (all four of which are True and Unicorn-verified).
CITRAS_DRIVER_WIRING_PORTED = True

# CITRAS_DRIVER_GRADIENT_WEIGHT_PORTED -- 0x10168f30, `ret 8`, thiscall
# (this, source /*i16 plane operand*/, dest /*u8 plane operand*/).
#
# docs/66's SEVENTH pass concluded this function "is not an independently
# callable function -- it is a compiler-outlined fragment sharing the
# DRIVER's own stack frame", on two stated grounds: (a) its `ret 8` "pops 8
# bytes of arguments the driver's real call site never pushes", and (b) it
# reads `[esp+0x70]` for its input-plane pointer, an address never written
# inside its own body. BOTH observations were real; the CONCLUSION drawn from
# them was wrong, and this pass disproved it by simply calling the function.
#   (a) The driver DOES push two dwords for it -- at 0x10169a87 and
#       0x10169a98, via the same `push ecx; mov ecx,esp; push &src; call
#       0x1003bf80` smart-pointer copy-construct idiom it uses for every
#       other operand argument in the function. That idiom's pushes are not
#       visually obvious as arguments (the pushed value is immediately
#       overwritten by the copy ctor), which is presumably how pass 7 missed
#       them.
#   (b) `[esp+0x70]` is not a local at all: the function's own prologue is
#       `sub esp,0x50` plus four register pushes, putting its first stack
#       argument at exactly [esp+0x70] and its second at [esp+0x74] -- and it
#       reads [esp+0x74] too, at 0x10169112, for the destination operand.
#
# Called standalone under Unicorn with the SAME operand-mocking discipline
# pakon_citras_apply_golden.py already uses for virtual_60/virtual_64 (own
# vtable slot 0x18 getOffset; sub-object 0x40 with slot 0x24 getPtr and slot
# 0x28 count(1,0)/(0,1)), it runs cleanly to completion and returns 0. Eight
# cases, all bit-exact against `gradient_weight` below -- see
# pakon_citras_driver_golden.py.
CITRAS_DRIVER_GRADIENT_WEIGHT_PORTED = True

# CITRAS_DRIVER_GAUSSIAN_KERNEL_PORTED -- 0x10168d90, __cdecl(out**, double
# sigma), verified live under Unicorn (kernel LENGTH, the exp() argument, and
# the sum-normalisation are all exact for every sigma tested: 0.5, 1.0, 2.5,
# 3.0, 8.25, 12.0).
#
# NOT bit-exact, and deliberately flagged as such rather than rounded up: the
# DLL computes exp() with the x87 `fldl2e`/`f2xm1`/`fscale` sequence in 80-bit
# extended precision and normalises by an 80-bit reciprocal, so its stored
# doubles differ from `math.exp` by up to 1 ULP (~1e-16 relative; measured, 4
# of 49 entries differ at sigma=8.25). For the ONE sigma the shipped
# CN-Enhanced op actually uses -- 8.25, a built-in constant with no .dpi
# source -- the exact 49 DLL-produced doubles are embedded verbatim as
# VENDOR_KERNEL_SIGMA_8_25 below and used directly, so the production path IS
# bit-exact; `gaussian_kernel` falls back to the formula for any other sigma
# and says so.
CITRAS_DRIVER_GAUSSIAN_KERNEL_PORTED = True


# ---------------------------------------------------------------------------
# citras op parameters, as ImaI16CitrasOp's ctor lays them out at this+0x110
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CitrasOpParams:
    """``this->0x110..0x128``, in the ctor's own field order/offsets.

    Defaults are the literal block at ``0x1058f4e8`` (read out of ``.rdata``,
    see the module docstring), plus ``do_clipping`` which the ctor hard-codes
    to 1 rather than reading from the block.
    """

    sigma: float = 8.25                     # f64 @ 0x110
    block_size: int = 8                     # i32 @ 0x118
    min_avoidance: int = 70                 # u8  @ 0x11c
    max_gradient: int = 4095                # i16 @ 0x11e
    low_gradient_threshold: int = -1        # i16 @ 0x120
    high_gradient_threshold: int = -1       # i16 @ 0x122
    do_clipping: int = 1                    # u8  @ 0x124
    min_value: int = 0                      # i16 @ 0x126
    max_value: int = 4095                   # i16 @ 0x128


# ---------------------------------------------------------------------------
# small integer helpers, matching the DLL's own idioms
# ---------------------------------------------------------------------------


def _wrap16(a: np.ndarray) -> np.ndarray:
    """Signed 16-bit wraparound, vectorised form of ``ca._wrap16``."""
    return ((a.astype(np.int64) + 0x8000) & 0xFFFF).astype(np.int64) - 0x8000


def _wrap32(a: np.ndarray) -> np.ndarray:
    """Signed 32-bit wraparound -- what an x86 ``imul``/``add`` on 32-bit
    registers actually produces, where numpy's int64 would widen instead."""
    return ((a.astype(np.int64) + 0x80000000) & 0xFFFFFFFF) - 0x80000000


def _trunc_div(n: np.ndarray, d: int) -> np.ndarray:
    """C's ``/`` for signed integers -- round toward zero, vectorised.

    numpy's ``//`` floors, which differs from C for negative dividends; this
    is the same correction ``ca._trunc_div100``/``ca._trunc_div3`` make
    scalar-wise, and every one of those is separately Unicorn-verified
    against the DLL's magic-multiply idiom.
    """
    n = n.astype(np.int64)
    q = np.abs(n) // d
    return np.where(n < 0, -q, q)


def _ftol(x: float) -> int:
    """``_ftol2`` (``0x104ffe44``) -- truncate toward zero."""
    return int(x)


# ---------------------------------------------------------------------------
# 0x10168d90 -- the normalised 1-D Gaussian kernel
# ---------------------------------------------------------------------------

def gaussian_radius(sigma: float) -> int:
    """``r`` at ``0x1016958f``..``0x101695a6`` and ``0x10168dbc``..``0x10168dc8``.

    The DLL computes ``n = _ftol2(sigma * -3.0)`` then ``length = 1 - 2n``
    (``shl eax,1`` / ``mov eax,1`` / ``sub eax,ecx``) and ``r = length/2``
    truncating (``cdq`` / ``sub eax,edx`` / ``sar eax,1``). For sigma > 0 that
    is exactly ``trunc(3*sigma)``, but the identity is only written out here;
    the arithmetic below is the DLL's, sign-for-sign, so a negative or zero
    sigma degrades the same way it does in the DLL rather than differently.
    """
    n = _ftol(sigma * SIGMA_TO_RADIUS_CONST)
    length = 1 - 2 * n
    return _ftol(length / 2) if length >= 0 else -_ftol(-length / 2)


#: The exact 49 doubles ``0x10168d90`` produces for the shipped CN-Enhanced
#: sigma (8.25), captured from real DLL execution under Unicorn. Embedded
#: rather than recomputed because the DLL's x87 80-bit ``exp`` differs from
#: ``math.exp`` by up to 1 ULP -- see CITRAS_DRIVER_GAUSSIAN_KERNEL_PORTED.
VENDOR_KERNEL_SIGMA: float = 8.25
VENDOR_KERNEL_SIGMA_8_25: tuple[float, ...] = (
    0.0007048053080374048, 0.0009954476112820658, 0.0013854371616296047,
    0.001900091160190667, 0.0025679184261579602, 0.0034198510490572953,
    0.004487994740426867, 0.005803856538684475, 0.00739605581007829,
    0.009287586499807213, 0.011492770773865691, 0.014014118934936405,
    0.016839377555815722, 0.019939095385275895, 0.023265053133203924,
    0.026749879355115636, 0.030308105319509792, 0.033838798084257764,
    0.0372297612728758, 0.04036312240920416, 0.04312195477420756,
    0.04539743397508645, 0.047095927339090515, 0.04814537580690002,
    0.048500363150605685, 0.04814537580690002, 0.047095927339090515,
    0.04539743397508645, 0.04312195477420756, 0.04036312240920416,
    0.0372297612728758, 0.033838798084257764, 0.030308105319509792,
    0.026749879355115636, 0.023265053133203924, 0.019939095385275895,
    0.016839377555815722, 0.014014118934936405, 0.011492770773865691,
    0.009287586499807213, 0.00739605581007829, 0.005803856538684475,
    0.004487994740426867, 0.0034198510490572953, 0.0025679184261579602,
    0.001900091160190667, 0.0013854371616296047, 0.0009954476112820658,
    0.0007048053080374048,
)


def gaussian_kernel(sigma: float) -> np.ndarray:
    """``0x10168d90``'s output: a ``2r+1``-entry kernel summing to 1.

    ``kernel[i] = exp(-(i-r)^2 / (2*sigma^2))``, then divided by the sum
    (``fdivr 1.0`` at ``0x10168e46``, then one multiply per entry). For
    ``sigma == 8.25`` the verbatim DLL doubles are returned instead of the
    recomputed ones -- see CITRAS_DRIVER_GAUSSIAN_KERNEL_PORTED for why.
    """
    if sigma == VENDOR_KERNEL_SIGMA and VENDOR_KERNEL_SIGMA_8_25:
        return np.array(VENDOR_KERNEL_SIGMA_8_25, dtype=np.float64)
    r = gaussian_radius(sigma)
    k = -1.0 / (2.0 * sigma * sigma)
    xs = np.arange(-r, r + 1, dtype=np.float64)
    vals = np.exp(k * xs * xs)
    return vals / vals.sum()


# ---------------------------------------------------------------------------
# 0x10168f30 -- the gradient-driven avoidance weight plane
# ---------------------------------------------------------------------------


def avoidance_table(p: CitrasOpParams) -> tuple[np.ndarray, int, int]:
    """``0x10168f30``'s own ``maxGradient+1``-entry byte table.

    Built at ``0x10168f4e``..``0x101690c2``: flat ``100`` up to
    ``lowThreshold``, a cosine ease down to ``minAvoidance`` between the two
    thresholds, flat ``minAvoidance`` above ``highThreshold``. Both
    thresholds have sigma-derived defaults when their parameter is negative.
    Returns ``(table, lowThreshold, highThreshold)``.
    """
    hi = p.high_gradient_threshold
    if hi < 0:                                   # 0x10168f91 test bp,bp / jge
        hi = _ftol(HIGH_THRESHOLD_CONST / (p.sigma * p.sigma))   # 0x10168f9b
    if hi < 1:                                   # 0x10168fb4 cmp bp,1
        hi = 1
    elif hi > p.max_gradient:                    # 0x10168fc1 cmp bp,di
        hi = p.max_gradient
    lo = p.low_gradient_threshold
    if lo < 0:                                   # 0x10168fc8 test bx,bx / jge
        lo = _ftol(hi * LOW_THRESHOLD_SCALE - LOW_THRESHOLD_BIAS)  # 0x10168fd4
        if lo < 0:                               # 0x10168feb
            lo = 0

    table = np.empty(p.max_gradient + 1, dtype=np.uint8)
    i = 0
    if lo >= 0:                                  # 0x10168ff7 test edx,edx / jl
        table[:lo + 1] = 100                      # 0x10169007 rep stosd 0x64646464
        i = lo + 1
    if lo != hi:                                 # 0x10169018 cmp bx,bp / je
        amp = (100 - p.min_avoidance) * 0.5       # fmul qword [0x10574f40] == 0.5
        step = 3.14159265 / (hi - lo)              # fdivr qword [0x1057fba0]
        idx = np.arange(i, hi)
        if idx.size:
            # 0x10169060..0x1016907d, in the DLL's own operation order:
            #   trunc((cos((i-lo)*step) + 1.0) * amp + minAvoidance + 0.5)
            vals = (np.cos((idx - lo) * step) + 1.0) * amp
            vals = vals + p.min_avoidance + 0.5
            table[i:hi] = np.trunc(vals).astype(np.uint8)
        i = hi
    if i <= p.max_gradient:                       # 0x10169094 cmp esi,ecx / jg
        table[i:] = p.min_avoidance                # 0x101690bb rep stosd
    return table, lo, hi


def gradient_weight(src: np.ndarray, p: CitrasOpParams) -> np.ndarray:
    """``0x10168f30``'s per-pixel half -- Unicorn-verified bit-exact.

    ``src`` is an ``(rows, cols)`` int16 plane; the result is the same shape,
    uint8. Per pixel, from ``0x10169220``..``0x10169289``::

        m = (cur - src[r][c+1])**2 + (cur - src[r+1][c])**2   # 32-bit signed
        if m > maxGradient: m = maxGradient
        out[r][c] = table[m]

    The final column of every row and the whole final row get
    ``minAvoidance`` instead (``0x1016928f`` and ``0x101692d0``) -- there is
    no forward neighbour there, and the DLL does not wrap or replicate.
    """
    if not CITRAS_DRIVER_GRADIENT_WEIGHT_PORTED:
        raise RuntimeError(
            "CITRAS_DRIVER_GRADIENT_WEIGHT_PORTED is False -- "
            f"{GRADIENT_WEIGHT_FN:#x} (ImaCitrasOpBase gradient weight) is "
            "not ported; see this module's flag comment.")

    table, _lo, _hi = avoidance_table(p)
    rows, cols = src.shape
    out = np.full((rows, cols), p.min_avoidance, dtype=np.uint8)
    if rows < 2 or cols < 2:
        return out
    cur = src[:-1, :-1].astype(np.int64)
    dx = cur - src[:-1, 1:].astype(np.int64)
    dy = cur - src[1:, :-1].astype(np.int64)
    # The DLL squares and sums in 32-bit registers (`imul eax,eax` /
    # `imul ebp,ecx` / `add eax,ebp` at 0x1016923e..0x10169248), so model the
    # 32-bit signed wraparound rather than numpy's widening. Unreachable on
    # real data -- the plane feeding this is the Gauss-blurred reference,
    # already clamped to [minValue, maxValue] == [0, 4095], so m <= 2*4095**2
    # -- but modelled anyway so the port does not quietly disagree with the
    # DLL on an input the DLL can be handed.
    m = _wrap32(_wrap32(dx * dx) + _wrap32(dy * dy))
    np.minimum(m, p.max_gradient, out=m)     # 0x1016924a cmp eax,ecx / jle
    # DELIBERATE DIVERGENCE FROM VENDOR UB, same family as the tone-table
    # index clamp this module's docstring documents: the `cmp/jle` above is a
    # SIGNED compare with no lower bound, so a wrapped-negative m sends the
    # DLL's `mov al, byte ptr [ecx+eax]` (0x10169254) reading below the
    # table. Clamping at 0 instead is the only defensible reproducible
    # choice; it cannot change any result on data the driver actually
    # produces (see above).
    np.maximum(m, 0, out=m)
    out[:-1, :-1] = table[m]
    return out


# ---------------------------------------------------------------------------
# 0x10154ea0 -- ImaBlockAverageOp's per-block compute
# ---------------------------------------------------------------------------


def block_average(src: np.ndarray, factor: int) -> np.ndarray:
    """Non-overlapping ``factor x factor`` box downsample, correctly rounded.

    ``src`` must be exactly ``(BH*factor, BW*factor)``; the result is
    ``(BH, BW)`` int16. The source rectangle for output cell ``(R, C)`` is
    ``{factor*R, factor*C, factor, factor}`` -- all four rect fields are
    multiplied by ``factor`` at ``0x10154eda``/``0x10154ee0``/``0x10154f49``/
    ``0x10154f4c``.

    Rounding, from the ``factor == 2`` integer fast path
    (``0x101550ac``..``0x101550c0``) and the general x87 path
    (``0x1015519d``..``0x101551b4``), which agree: the bias is
    ``floor(factor**2 / 2)`` (materialised at ``0x1015500a``..``0x10155017``,
    constant-folded to the literal ``2`` in the ``factor == 2`` path), it is
    added BEFORE the division with the sign of the sum, and the division
    truncates toward zero. The store is ``mov word ptr [...], ax`` in both
    paths -- low 16 bits, no clamp, no saturation.
    """
    rows, cols = src.shape
    if rows % factor or cols % factor:
        raise RuntimeError(
            f"block_average: {rows}x{cols} is not a multiple of "
            f"factor={factor}; the driver always pads to one first "
            f"(0x10169561..0x1016958b) -- a caller that does not is a bug.")
    bh, bw = rows // factor, cols // factor
    s = (src.astype(np.int64)
         .reshape(bh, factor, bw, factor)
         .sum(axis=(1, 3)))
    half = (factor * factor) // 2
    n = s + np.where(s >= 0, half, -half)
    q = _trunc_div(n, factor * factor)
    return _wrap16(q).astype(np.int16)


# ---------------------------------------------------------------------------
# the driver's own arithmetic, vectorised
# ---------------------------------------------------------------------------


def luminance(img: np.ndarray) -> np.ndarray:
    """``virtual_64`` (``0x10168800``), vectorised.

    ``(R + G + B + 1) / 3``, truncating toward zero, stored as int16. The
    scalar, DLL-verified original is
    ``pakon_citras_apply.apply_luminance``; ``pakon_citras_driver_golden.py``
    proves this form agrees with it.
    """
    total = (img[..., 0].astype(np.int64) + img[..., 1].astype(np.int64)
             + img[..., 2].astype(np.int64) + 1)
    return _wrap16(_trunc_div(total, 3)).astype(np.int16)


def avoidance_blend(reference: np.ndarray, weight: np.ndarray,
                    value: np.ndarray, table: np.ndarray) -> np.ndarray:
    """``virtual_60`` (``0x10168360``), vectorised, returning the DELTA plane.

    ``table`` is the ``Tsc1DLutT`` contents -- ``lutSize`` signed-16-bit
    entries, bias 0 (see the module docstring for the construction trace).
    The DLL bias-subtracts the table in place for the duration of the call,
    so what it stores is ``wrap16(table[idx] - idx)``; that subtraction is
    folded in here rather than modelled as a mutate/restore pair, which is
    equivalent because ``idx`` is the same value on both sides.

    The scalar, DLL-verified original is
    ``pakon_citras_apply.apply_avoidance_blend``.
    """
    p = value.astype(np.int64)
    ref = reference.astype(np.int64)
    diff = _wrap16(p - ref)
    weighted = weight.astype(np.int64) * diff + 50
    q = _trunc_div(weighted, 100)
    idx = _wrap16(p - q)
    # Deliberate divergence from vendor UB -- see the module docstring's
    # "shared tone table" section. The DLL indexes `table` with the raw
    # wrapped idx and reads adjacent heap outside [0, lutSize-1].
    idx = np.clip(idx, 0, table.size - 1)
    return _wrap16(table[idx].astype(np.int64) - idx).astype(np.int16)


def tone_compose(img: np.ndarray, base: np.ndarray,
                 p: CitrasOpParams) -> np.ndarray:
    """``virtual_56`` (``0x10167bf0``), vectorised.

    ``base`` is 1-band and broadcasts across all three of ``img``'s bands
    (``min(band, base.band_count - 1)``, already Unicorn-verified). ``img``
    is what the DLL mutates in place; this returns a new array instead, which
    the render path wants anyway.

    The scalar, DLL-verified original is
    ``pakon_citras_apply.apply_tone_compose``.
    """
    s = _wrap16(img.astype(np.int64) + base.astype(np.int64)[..., None])
    if p.do_clipping:
        s = np.clip(s, p.min_value, p.max_value)
    return s.astype(np.int16)


# ---------------------------------------------------------------------------
# 0x10155290 (i16) / 0x101556a0 (u8) -- the separable upsample
# ---------------------------------------------------------------------------

UPSAMPLE_I16 = 0x10155290
UPSAMPLE_U8 = 0x101556A0


def _upsample_axis(s: np.ndarray, r: int, dtype_bits: int) -> np.ndarray:
    """One pass of ``0x10155290``/``0x101556a0`` along the LAST axis.

    ``s`` is ``(lines, N)``; the result is ``(lines, N*r)``. The kernels
    (``0x10154110``/``0x10154300`` for i16, ``0x10154500``/``0x101546c0`` for
    u8 -- chosen by ``r & 1``) run a backwards integer DDA, but every variant
    computes the same closed form, for destination index ``j``::

        i   = clamp(floor((2j + 1 - r) / (2r)), 0, N-2)
        ACC = 2r*s[i] + (2j + 1 - r - 2r*i) * (s[i+1] - s[i]) + r
        out[j] = trunc_toward_zero(ACC / (2r))

    i.e. **linear interpolation on half-pixel centres**, rounded by the ``+r``
    (== +0.5 of a destination step) and then truncated by the ``cdq``/``idiv``
    pair -- NOT symmetric rounding: for a negative quotient the ``+r`` biases
    upward. Outside ``[0, N-1]`` the source index is clamped but the VALUE is
    not: the two end intervals' slopes are extrapolated, so edge outputs can
    legitimately go below the source's own minimum (and, for the u8 plane,
    wrap modulo 256 -- the store is a plain ``mov byte ptr``, no saturation).

    ``dtype_bits`` selects that wraparound width (16 or 8), matching the two
    kernels' stores.
    """
    lines, n = s.shape
    if n < 2:
        raise RuntimeError(
            f"_upsample_axis: N={n}; the DLL's kernels unconditionally read "
            "s[N-2] and would dereference one element before the plane. The "
            "driver never produces N<2 (it feeds them BW/BH, both >= 2 for "
            "any real frame) -- a caller that does is a bug, not a case to "
            "emulate.")
    d = 2 * r
    j = np.arange(n * r, dtype=np.int64)
    t = j * 2 + 1 - r
    i = np.clip(t // d, 0, n - 2)                 # floor, then clamp
    lo = s[:, i].astype(np.int64)
    hi = s[:, i + 1].astype(np.int64)
    acc = d * lo + (t - d * i)[None, :] * (hi - lo) + r
    out = _trunc_div(acc, d)
    if dtype_bits == 16:
        return _wrap16(out).astype(np.int16)
    return (out & 0xFF).astype(np.uint8)


def upsample(src: np.ndarray, rx: int, ry: int) -> np.ndarray:
    """``0x10155290``/``0x101556a0``: expand by integer ratios, two passes.

    Pass 1 expands X on ``src``'s own ``srcH`` rows (``0x101554e7``/
    ``0x10155512``); pass 2 then expands Y **in place on the destination**
    (``0x1015553b``/``0x10155542``, with the destination's row/column strides
    swapped so the kernel walks columns). Doing pass 2 on the already-widened
    rows -- not on the original -- is what makes the two passes separable
    rather than independent, and is why this function chains them rather than
    expanding both axes from ``src``.

    Both ratios must divide exactly (``0x10155435``/``0x1015544c``); the
    wrapper returns ``-4`` otherwise and this raises instead of silently
    approximating.
    """
    if rx < 1 or ry < 1:
        raise RuntimeError(f"upsample: ratios must be >= 1, got {rx}x{ry} "
                           "(the DLL's own idiv-exactness gate, 0x10155421)")
    bits = 16 if src.dtype == np.int16 else 8
    wide = _upsample_axis(src, rx, bits)                 # pass 1: X
    tall = _upsample_axis(np.ascontiguousarray(wide.T), ry, bits).T
    return np.ascontiguousarray(tall)


# ---------------------------------------------------------------------------
# 0x1014f7d0 / 0x10016d60 -- ImaPadOpT<short>, pad mode 2 == MIRROR
# ---------------------------------------------------------------------------

PAD_OP_CTOR = 0x1014F7D0
PAD_OP_COMPUTE = 0x10016D60


def mirror_pad(src: np.ndarray, left: int, right: int, top: int,
               bottom: int) -> np.ndarray:
    """``ImaPadOpT<short>`` in ``MIRROR`` mode.

    The driver constructs this operator twice, both times with the literal
    ``2`` as its ``padMode`` argument (``0x10169754`` and ``0x101698eb``).
    ``2`` is ``MIRROR``: the mode-name table at ``0x106a3924`` -- the one the
    string-to-enum parser at ``0x10300150`` walks, raising
    ``"Unknown ImaPadOp::Pad"`` on a miss -- reads
    ``{CONSTANT, EXTEND, MIRROR, WRAP, JUNK, COPY, SHRINK}``, and the compute
    body's own jump table at ``0x10017c10`` sends index 2 to ``0x100173dd``.

    The index arithmetic there (``0x1001754a``..``0x100175a9``) is::

        srcY = abs(abs((y + H - 1) % (2H - 2)) - (H - 1))
        srcX = abs(abs((x + W - 1) % (2W - 2)) - (W - 1))

    -- period ``2N-2``, i.e. reflection that does **not** repeat the edge
    sample (numpy's ``mode="reflect"``; OpenCV's ``BORDER_REFLECT_101``). The
    inner loop makes that explicit by reversing direction only *after*
    emitting the boundary column (``0x10017607`` ``cmp esi, ebx`` /
    ``0x10017615``). The sample itself is copied verbatim -- ``mov ax, word
    ptr [eax]`` / ``mov word ptr [ecx], ax``, no arithmetic.

    The four margins are ``left, right, top, bottom`` in the ctor's own
    argument order, established from the geometry method ``0x10300050``
    (``newW = W + this->0x110 + this->0x10c`` with ``origin.x += 0x10c``, so
    ``0x10c`` is the BEFORE margin on x, and likewise ``0x114`` on y).
    """
    if left or right or top or bottom:
        return np.pad(src, ((top, bottom), (left, right)), mode="reflect")
    return src


# ---------------------------------------------------------------------------
# 0x100a4010 / 0x100a4220 -- ImaConvolutionSeparableOpT<short>
# ---------------------------------------------------------------------------

CONVOLUTION_CTOR = 0x100A4010
CONVOLUTION_COMPUTE = 0x100A4220


def gauss_blur(src: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """``ImaConvolutionSeparableOpT<short>``'s compute (``0x100a4220``).

    A "valid" separable convolution: the output is ``srcH - kh + 1`` by
    ``srcW - kw + 1`` (``0x102ff3b3`` ``sub eax,[esi+0x18]`` / ``inc eax``),
    with NO border rule of its own -- it simply consumes the ``r``-pixel
    mirror pad the ``ImaPadOpT`` above already produced, which is why the
    driver pads by exactly ``r`` first and gets back a plane the same size as
    the block grid.

    Pass order is **vertical first** (``0x100a43d0``, taps = kernel height,
    tap step = the row stride, run across the full source width into a
    ``double`` line buffer) then **horizontal** out of that buffer
    (``0x100a4430``). ``0x10168d90`` hands the SAME array in as both the row
    and the column kernel (``push edi; push edi; push esi; push esi`` at
    ``0x10168eb8``), so one 1-D Gaussian serves both axes.

    Write-back (``0x100a447b``..``0x100a449b``): ``acc + 0.5`` if
    ``acc >= 0`` else ``acc - 0.5``, then ``_ftol2`` truncation toward zero
    -- round-half-AWAY-from-zero -- and ``mov word ptr [edi], ax``, low 16
    bits, **no saturation**.

    NO CLAMP HAPPENS HERE, despite ``minValue``/``maxValue`` being passed in.
    The clip flag is ``this->0x13``, set from the ctor's sixth argument, and
    the driver pushes ``esi`` for it at ``0x10169968`` where ``esi`` is still
    ``0`` from the ``xor esi, esi`` at ``0x1016989f``. So the branch at
    ``0x100a4457`` always skips the clamp and the two bounds are stored but
    never applied. This was worth checking rather than assuming: passing
    those two parameters and then not using them is exactly the shape that
    invites a wrong guess.

    PRECISION, STATED PLAINLY: the DLL accumulates both passes on the x87
    stack in 80-bit extended precision (``fld 0.0`` / ``fild`` or ``fld
    qword`` / ``fmul`` / ``faddp``), rounding to ``double`` only when pass 1
    stores its line buffer. numpy accumulates in 64-bit. The tap ORDER is
    identical (this function adds tap ``k`` for every pixel before tap
    ``k+1``, matching the DLL's own inner loops), so the only difference is
    intermediate rounding, ~1e-13 absolute at these magnitudes. That can
    only change an output where the accumulator lands within that distance
    of a ``.5`` boundary. This is NOT claimed to be bit-exact, and it is the
    one arithmetic stage of this driver that isn't.
    """
    kh = kw = kernel.size
    src_h, src_w = src.shape
    out_h, out_w = src_h - kh + 1, src_w - kw + 1
    if out_h <= 0 or out_w <= 0:
        raise RuntimeError(
            f"gauss_blur: {src_h}x{src_w} source with a {kh}-tap kernel "
            f"leaves a {out_h}x{out_w} valid region; the driver always pads "
            "by the kernel radius first (0x10169922).")
    tmp = np.zeros((out_h, src_w), dtype=np.float64)
    srcf = src.astype(np.float64)
    for k in range(kh):                      # 0x100a43e0..0x100a43f6
        tmp += kernel[k] * srcf[k:k + out_h, :]
    acc = np.zeros((out_h, out_w), dtype=np.float64)
    for k in range(kw):                      # 0x100a4440..0x100a444a
        acc += kernel[k] * tmp[:, k:k + out_w]
    biased = acc + np.where(acc >= 0.0, 0.5, -0.5)
    return _wrap16(np.trunc(biased).astype(np.int64)).astype(np.int16)


# ---------------------------------------------------------------------------
# the whole driver
# ---------------------------------------------------------------------------


def apply_citras(img: np.ndarray, tone_lut, p: CitrasOpParams | None = None
                 ) -> np.ndarray:
    """``ImaCitrasOpBase::virtual_40`` (``0x10169350``), end to end.

    ``img`` is an ``(H, W, 3)`` int16 array -- the 3-band operand the DLL
    pre-fills from ``this->0x104`` and then mutates in place. ``tone_lut`` is
    ``analyzeAutoTone``'s composed curve, exactly the array
    ``AnsCitrasOperand::setToneLut`` copies and ``AnsImaCitrasAggregate``'s
    ctor wraps in the ``Tsc1DLutT`` that becomes ``this->0x108``. Returns a
    new ``(H, W, 3)`` int16 array rather than mutating in place.

    Every line below carries the VA it came from in this module's docstring;
    read that first, it is the actual finding.
    """
    if not CITRAS_DRIVER_WIRING_PORTED:
        raise RuntimeError(
            "CITRAS_DRIVER_WIRING_PORTED is False -- "
            f"{CITRAS_DRIVER:#x} (ImaCitrasOpBase::virtual_40) is not "
            "ported; see this module's flag comment.")
    p = p or CitrasOpParams()
    if img.ndim != 3 or img.shape[2] != 3:
        raise RuntimeError(
            f"apply_citras: expected an (H, W, 3) image, got {img.shape}. "
            "The driver validates 3 bands on both operands at 0x101693eb "
            "and 0x101693f4 and refuses anything else.")
    img = img.astype(np.int16, copy=False)
    height, width = img.shape[0], img.shape[1]
    bs = p.block_size
    radius = gaussian_radius(p.sigma)
    bw = -(-width // bs)
    bh = -(-height // bs)
    pad_w, pad_h = bw * bs, bh * bs

    lum = luminance(img)                                     # 0x101696c6
    padded = mirror_pad(lum, 0, pad_w - width, 0, pad_h - height)  # 0x1016977c
    blk = block_average(padded, bs)                          # 0x10169861
    ext = mirror_pad(blk, radius, radius, radius, radius)    # 0x10169922
    kernel = gaussian_kernel(p.sigma)                        # 0x1016994a
    smooth = gauss_blur(ext, kernel)                         # 0x101699d7
    weight_low = gradient_weight(smooth, p)                  # 0x10169a9f

    reference = upsample(smooth, bs, bs)[:height, :width]    # 0x10169af7
    weight = upsample(weight_low, bs, bs)[:height, :width]   # 0x10169b7d

    table = np.asarray(tone_lut, dtype=np.int64)
    delta = avoidance_blend(reference, weight, lum, table)   # 0x10169bf3
    return tone_compose(img, delta, p)                       # 0x10169c30
