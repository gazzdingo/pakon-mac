#!/usr/bin/env python3
"""Golden FLESH **weight plane + shift-LUT pre-passes** vs PakonIMAu.dll.

The three earlier flesh harnesses each closed one stage and each ended by
naming the same two remaining items as *inputs* rather than stages:

* `pakon_flesh_golden.py`            -> the adjust arithmetic (tier 1)
* `pakon_flesh_detector_golden.py`   -> border / LST / clamp / reduction
* `pakon_flesh_threshold_golden.py`  -> `fcn.1029ec50` and `fcn.1029cad0`

  "still missing: the analysis-image construction (`0x104e8360`,
   `0x1014cc20`, `0x104e7880`) and the two 1-D LUT pre-passes at
   `0x10270920` / `0x10270b10`"

This harness closes both, and corrects the description of the first.

WHAT THE EARLIER PASSES HAD WRONG
=================================

1. **`0x104e7880` is not part of the analysis-image construction and is not
   a resampler.**  It is `.\\IemPad.cpp` -- the DLL's own string, at
   `0x104e79ca`: *"Output rows/cols must be equal to or greater than input
   rows/cols"*.  `0x1027127e` uses it to bring the **weight plane** up to
   the analysis image's dimensions, and it is a centred **replicate** pad,
   not a zero fill and not an interpolation.  Section [2] shows this rather
   than asserting it: a constant-fill port disagrees on 1,472 of 3,191
   samples and is reported.

2. **`0x104e8360` never runs on the shipped DPI.**  All four call sites
   (`0x102704f4`, `0x10270545`, `0x102705c6`, `0x10270606`) sit under
   `0x102704a9 test cl, cl` on ``params+0x60a9`` = ``useSmallAnalysisImage``,
   which the shipped DPI sets to **0**.  Section [5] asserts that from the
   parsed DPI.

3. **What actually builds the weight plane is `fcn.10271bc0`**, called once
   from `AnsFleshCapabilityImpl::analyze` at `0x101c99f0` -- the call whose
   failure path prints *"Could not generate weight map; status ="*.  It is a
   2-D **Gaussian**, peak 1000 at the image centre, sigma set by
   ``axialProb`` and ``clipAmount``, evaluated over the clip-inset region.
   Section [1] runs the real function.

4. **The two 1-D LUT pre-passes are the shift triple.**  `0x102707e8` builds
   three LUTs ``clamp(i + shift_c, 0, 4095)`` from `fcn.10270280`'s own
   **arg6** -- the very triple `analyzePostBalance` is about to add Delta to
   -- and `0x10270920` applies them to the analysis image in place.  So the
   flesh detector measures the frame **as it would look with the candidate
   balance applied**.  Sections [3] and [4].

WHAT THIS PROVES
================

Bit-exact against the real DLL, executed under Unicorn with nothing patched
except the CRT surface `pakon_flesh_threshold_golden.Guest` already provides:

* `flesh_weight_map`         `fcn.10271bc0`   3,078,017 samples
* `flesh_pad_replicate`      `fcn.104e7880`   every sample of 8 shapes
* `flesh_shift_lut`          `fcn.1026fed0` + `fcn.10270050`
* `flesh_apply_shift_luts`   `0x102708ba…0x10270979` AND `0x10270ab9…0x10270b69`

WHAT IT DOES **NOT** PROVE
==========================

* **The x87 transcendental.**  `0x10271e26…0x10271e3a` is
  ``fldl2e/fmulp/frndint/f2xm1/fld1/faddp/fscale``, and under Unicorn that
  is QEMU's `f2xm1`, not a Pentium's.  The port uses `math.exp`.  Section
  [1] measures the disagreement over 3 M samples and it is **zero**, but a
  zero difference against an emulated transcendental is evidence about
  Unicorn, not about the silicon; it is reported as such.
* **The composition** `flesh_reduction_weight_plane`.  `fcn.10271bc0` is
  called with dimensions from an object outside the capability and the pad
  with the analysis image's own -- this port can only build the case where
  they agree.  Tier 3, stated in the docstring.
* **Which images arg3 and arg4 are.**  They come from
  `AnsImageData::copyToIemImage` (`fcn.100db520`) at `0x101c9bac` /
  `0x101c9beb`.  A boundary, not a stage.
* **arg7 (exposure) and arg8 (second pre-pass)** -- caller state.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \\
    tools/ansel/python-pipeline/pakon_flesh_weight_golden.py [PakonIMAu.dll]``
"""
from __future__ import annotations

import hashlib
import struct
import sys
from dataclasses import replace
from pathlib import Path

from unicorn.x86_const import UC_X86_REG_EDI, UC_X86_REG_ESP

import pakon_flesh as fl
import pakon_flesh_detector_golden as det
import pakon_flesh_threshold_golden as thr

DEFAULT_DLL = thr.DEFAULT_DLL


# --- deterministic PRNG (the same one the other flesh harnesses use) --------


class Rng:
    def __init__(self, seed: int) -> None:
        self.s = seed & 0x7FFFFFFF

    def next(self) -> int:
        self.s = (self.s * 1103515245 + 12345) & 0x7FFFFFFF
        return self.s

    def between(self, lo: int, hi: int) -> int:
        return lo + self.next() % (hi - lo)


# --- 1. fcn.10271bc0, the Gaussian weight map -------------------------------


def run_dll_weight_map(g: "thr.Guest", params_addr: int, rows: int, cols: int):
    """``fcn.10271bc0(rows, cols, params, &image)`` -> (plane, status)."""
    obj = g.alloc(16)
    g.uc.mem_write(obj, b"\0" * 16)
    st = g.call(fl.FLESH_WEIGHT_MAP_FN, args=(rows, cols, params_addr, obj)) & 0xFFFF
    if st:
        return None, st
    impl = struct.unpack("<I", g.uc.mem_read(obj + 4, 4))[0]
    h, w = struct.unpack("<ii", g.uc.mem_read(impl + 0x10, 8))
    rp = struct.unpack("<I", g.uc.mem_read(impl + 0x18, 4))[0]
    out = []
    for y in range(h):
        p = struct.unpack("<I", g.uc.mem_read(rp + 4 * y, 4))[0]
        out.append(list(struct.unpack("<%dh" % w, g.uc.mem_read(p, 2 * w))))
    return out, 0


def _params_blob(g: "thr.Guest", params: fl.FleshParams) -> int:
    a = g.alloc(fl.FLESH_PARAM_BLOB_SIZE)
    g.uc.mem_write(a, bytes(params.to_bytes()))
    return a


def check_weight_map(g, base) -> tuple[int, list]:
    print("\n  [1] weight map  fcn.10271bc0  (0x10271de0 loop)")
    rng = Rng(0x0D15EA5E)
    dims = [(1, 1), (2, 2), (7, 9), (30, 30), (40, 60), (100, 150), (21, 21),
            (333, 501), (13, 4097), (2000, 3000), (41, 61), (99, 149)]
    #: the mutation set in [6] needs BOTH parities: `_sar1` only shows on odd
    #: dimensions, and a centre-rounding bug is invisible on even ones.
    probe_dims = {(40, 60), (100, 150), (41, 61), (99, 149)}
    dims += [(rng.between(1, 400), rng.between(1, 400)) for _ in range(12)]
    variants = {
        "shipped (axialProb=0.25, clip=0.30)": base,
        "axialProb=0.05": replace(base, axial_prob=0.05),
        "axialProb=0.90": replace(base, axial_prob=0.90),
        "clip=0.00": replace(base, clip_amount=0.0),
        "clip=0.45": replace(base, clip_amount=0.45),
    }
    fails = checked = 0
    cases = []
    for name, params in variants.items():
        pa = _params_blob(g, params)
        for rows, cols in dims:
            dll, st = run_dll_weight_map(g, pa, rows, cols)
            if st:
                print(f"      FAIL [{name}] {rows}x{cols}: dll status {st:#06x}")
                fails += 1
                continue
            host = fl.flesh_weight_map(rows, cols, params)
            if len(dll) != len(host) or (dll and len(dll[0]) != len(host[0])):
                print(f"      FAIL [{name}] {rows}x{cols}: dims "
                      f"{len(dll)}x{len(dll[0])} vs {len(host)}x{len(host[0])}")
                fails += 1
                continue
            n = 0
            for a, b in zip(dll, host):
                for u, v in zip(a, b):
                    checked += 1
                    n += u != v
            if n:
                fails += 1
                if fails <= 5:
                    print(f"      FAIL [{name}] {rows}x{cols}: {n} differ")
            if name.startswith("shipped") and (rows, cols) in probe_dims:
                cases.append((rows, cols, dll))
    print(f"      {checked} samples over {len(variants)} parameter variants "
          f"x {len(dims)} shapes: "
          f"{'ALL BIT-EXACT' if not fails else f'{fails} SHAPES FAILED'}")
    print("      The peak is 1000 at the centre (0x105a3c18) and the map covers")
    print("      only [b, dim-b) on each axis, b = flesh_border(dim, clipAmount).")
    print("      CAVEAT, reported not hidden: 0x10271e26..0x10271e3a is the x87")
    print("      fldl2e/frndint/f2xm1/fscale exp2 sequence.  Under Unicorn that is")
    print("      QEMU's f2xm1, not a Pentium's, so agreement here is evidence about")
    print("      the ALGEBRA around it (which is what the mutations in [6] probe)")
    print("      and not about the last ULP of the exponential on real silicon.")
    return fails, cases


# --- 2. fcn.104e7880, the pad -----------------------------------------------


def run_dll_pad(g: "thr.Guest", src_rows, rows: int, cols: int,
                mode: int = 1, fill: float = 0.0):
    src = g.new_image(src_rows)
    ret = g.alloc(16)
    g.uc.mem_write(ret, b"\0" * 16)
    lo, hi = struct.unpack("<II", struct.pack("<d", float(fill)))
    r = g.call(fl.FLESH_PAD_FN, args=(ret, src, rows, cols, mode, lo, hi))
    impl = struct.unpack("<I", g.uc.mem_read(r + 4, 4))[0]
    h, w = struct.unpack("<ii", g.uc.mem_read(impl + 0x10, 8))
    rp = struct.unpack("<I", g.uc.mem_read(impl + 0x18, 4))[0]
    return [
        list(struct.unpack("<%dh" % w, g.uc.mem_read(
            struct.unpack("<I", g.uc.mem_read(rp + 4 * y, 4))[0], 2 * w)))
        for y in range(h)
    ]


def check_pad(g) -> tuple[int, int]:
    print("\n  [2] pad  fcn.104e7880 -> fcn.104e7190  (operation 1)")
    rng = Rng(0x0BADF00D)
    shapes = [(4, 5, 4, 5), (4, 5, 10, 11), (3, 3, 9, 9), (30, 44, 40, 60),
              (7, 8, 8, 9), (1, 1, 5, 5), (2, 2, 7, 6), (17, 17, 21, 21)]
    fails = checked = 0
    zero_fill_would_differ = 0
    for sh, sw, rows, cols in shapes:
        src = [[rng.between(-1000, 1000) for _ in range(sw)] for _ in range(sh)]
        dll = run_dll_pad(g, src, rows, cols)
        host = fl.flesh_pad_replicate(src, rows, cols)
        n = 0
        for y in range(rows):
            for x in range(cols):
                checked += 1
                n += dll[y][x] != host[y][x]
        if n:
            fails += 1
            print(f"      FAIL {sh}x{sw} -> {rows}x{cols}: {n} differ")
        # the negative control: what a zero-fill port would have produced
        top = fl._sar1(rows - sh)
        left = fl._sar1(cols - sw)
        for y in range(rows):
            for x in range(cols):
                z = (src[y - top][x - left]
                     if 0 <= y - top < sh and 0 <= x - left < sw else 0)
                zero_fill_would_differ += z != dll[y][x]
    print(f"      {checked} samples over {len(shapes)} shapes: "
          f"{'ALL BIT-EXACT' if not fails else f'{fails} FAILED'}")
    print(f"      operation 1 is REPLICATE, measured: a constant-zero-fill port "
          f"would disagree on {zero_fill_would_differ}/{checked} samples.")
    # and the fill argument is inert for operation 1 -- shown, not assumed
    src = [[rng.between(-1000, 1000) for _ in range(4)] for _ in range(3)]
    a = run_dll_pad(g, src, 9, 10, fill=0.0)
    b = run_dll_pad(g, src, 9, 10, fill=-12345.0)
    print(f"      the `double` fill the call site pushes at 0x10271255 is "
          f"PROVABLY INERT here: fill 0.0 vs -12345.0 give "
          f"{'identical' if a == b else 'DIFFERENT'} planes.")
    if a != b:
        fails += 1
    return fails, checked


# --- 3. fcn.1026fed0 + fcn.10270050, the shift LUTs -------------------------


def run_dll_shift_luts(g: "thr.Guest", shifts, *, bits=fl.SHIFT_LUT_BITS,
                       lo=0, hi=0xFFF, count=fl.SHIFT_LUT_COUNT):
    master = g.alloc(16)
    g.uc.mem_write(master, b"\0" * 16)
    g.call(fl.FLESH_MASTER_TABLE_CTOR, ecx=master,
           args=(bits, lo & 0xFFFF, hi & 0xFFFF))
    outs = [g.alloc(4) for _ in range(3)]
    st = g.call(fl.FLESH_SHIFT_LUT_BUILDER, ecx=master,
                args=(outs[0], outs[1], outs[2], count,
                      shifts[0] & 0xFFFF, shifts[1] & 0xFFFF, shifts[2] & 0xFFFF))
    res = []
    for o in outs:
        p = struct.unpack("<I", g.uc.mem_read(o, 4))[0]
        res.append(list(struct.unpack("<%dh" % count, g.uc.mem_read(p, 2 * count))))
    return res, st & 0xFFFF


#: docs/74 §178's six measured `entry +0x4b6` triples, used as probes.
ENTRY_TRIPLES = (
    (742, 326, 60), (788, 371, 134), (852, 457, 188),
    (957, 556, 297), (658, 259, 24), (766, 357, 116),
)
#: and the six Deltas measured at the builder for those frames.
MEASURED_DELTAS = (-40, 34, 15, 35, -59, 13)


def check_shift_luts(g) -> int:
    print("\n  [3] shift LUTs  fcn.1026fed0(0xc,0,0xfff) + fcn.10270050")
    rng = Rng(0x5EA50)
    probes = list(ENTRY_TRIPLES) + [
        (0, 0, 0), (1, -1, 0), (-4095, 4095, 2048), (-2000, 3000, 4095),
        (4096, -4096, 1), (-8000, 8000, 0),
    ]
    probes += [(rng.between(-4000, 4000), rng.between(-4000, 4000),
                rng.between(-4000, 4000)) for _ in range(20)]
    fails = checked = 0
    for shifts in probes:
        dll, st = run_dll_shift_luts(g, shifts)
        if st:
            print(f"      FAIL {shifts}: builder status {st:#06x}")
            fails += 1
            continue
        for k in range(3):
            host = fl.flesh_shift_lut(shifts[k])
            n = sum(1 for a, b in zip(dll[k], host) if a != b)
            checked += len(host)
            if n:
                fails += 1
                bad = next(i for i in range(len(host)) if dll[k][i] != host[i])
                print(f"      FAIL shift {shifts[k]}: {n} differ, first at "
                      f"i={bad} dll={dll[k][bad]} host={host[bad]}")
    print(f"      {checked} LUT entries over {len(probes)} triples: "
          f"{'ALL BIT-EXACT' if not fails else f'{fails} FAILED'}")
    # the out-of-range guard, demonstrated against the DLL rather than assumed
    dll, _ = run_dll_shift_luts(g, (0x7FFF, 0, 0))
    try:
        fl.flesh_shift_lut(0x7FFF)
        print("      FAIL: shift 0x7fff should raise")
        fails += 1
    except ValueError:
        garbage = sum(1 for i in range(1, 0x1000) if dll[0][i] != 0xFFF)
        print(f"      shift 0x7fff runs fcn.10270050's index past the clamp "
              f"table: the DLL returns {garbage}/4095 entries that are not the "
              f"clamped value (heap garbage).  The port RAISES rather than "
              f"modelling it -- the same rule flesh_histogram already uses.")
    return fails


# --- 4. the two 1-D LUT pre-passes ------------------------------------------


def run_dll_prepass(pe: bytes, planes, luts, *, entry: int, exit_: int,
                    img_slot: int):
    """`0x102708ba…0x10270979` (img object at esp+0x3c) and its twin
    `0x10270ab9…0x10270b69` (object at esp+0x30).  Both read the three plane
    data blocks from ``[esp+0xa8] / [esp+0xb0] / [esp+0xb8]`` and the three
    LUTs from ``[esp+0x24] / [esp+0x38] / [esp+0x10]``."""
    g = det.Guest(pe)
    h = len(planes[0])
    w = len(planes[0][0])
    img = g.alloc(0x80)
    g.uc.mem_write(img + 0x14, struct.pack("<III", h, w, 3))
    blocks, rowptrs = [], []
    for pl in planes:
        d, ptrs = g.i16_rows(pl)
        blocks.append(d)
        rowptrs.append(ptrs)
    lut_addrs = [g.blob(struct.pack("<%dh" % len(l), *l)) for l in luts]
    esp = det.STACK_ADDR + 0x100000
    g.uc.reg_write(UC_X86_REG_ESP, esp)
    g.uc.reg_write(UC_X86_REG_EDI, 0)  # the y counter's seed at 0x102708c6
    g.uc.mem_write(esp + img_slot, struct.pack("<I", img))
    for off, b in zip((0xA8, 0xB0, 0xB8), blocks):
        g.uc.mem_write(esp + off, struct.pack("<I", b))
    for off, a in zip((0x24, 0x38, 0x10), lut_addrs):
        g.uc.mem_write(esp + off, struct.pack("<I", a))
    g.run(entry, exit_)
    return [
        [list(struct.unpack("<%dh" % w, g.uc.mem_read(p, 2 * w))) for p in ptrs]
        for ptrs in rowptrs
    ]


def check_prepass(pe: bytes) -> tuple[int, list]:
    print("\n  [4] 1-D LUT pre-passes  0x102708ba…0x10270979 and "
          "0x10270ab9…0x10270b69")
    rng = Rng(0x1CEB00DA & 0x7FFFFFFF)
    fails = checked = 0
    cases = []
    for shifts, (h, w) in zip(ENTRY_TRIPLES[:4],
                              ((7, 11), (1, 1), (13, 4), (5, 33))):
        luts = fl.flesh_shift_luts(shifts)
        planes = [[[rng.between(0, 4096) for _ in range(w)] for _ in range(h)]
                  for _ in range(3)]
        host = fl.flesh_apply_shift_luts(planes, luts)
        for label, entry, exit_, slot in (
            ("pre-pass 1 (arg4 image)", fl.FLESH_PREPASS1_ENTRY,
             fl.FLESH_PREPASS1_EXIT, 0x40),
            ("pre-pass 2 (arg3 image, arg8)", fl.FLESH_PREPASS2_ENTRY,
             fl.FLESH_PREPASS2_EXIT, 0x34),
        ):
            dll = run_dll_prepass(pe, planes, luts, entry=entry, exit_=exit_,
                                  img_slot=slot)
            checked += 3 * h * w
            if dll != host:
                fails += 1
                print(f"      FAIL [{label}] {shifts} {h}x{w}")
        cases.append((planes, luts, host))
    print(f"      {checked} samples: "
          f"{'ALL BIT-EXACT' if not fails else f'{fails} FAILED'}")
    print("      Both loops are the SAME arithmetic on different image slots, which")
    print("      is why one port covers both: plane0<-[esp+0x24], plane1<-[esp+0x38],")
    print("      plane2<-[esp+0x10], the three LUTs 0x102707e8 built from arg6.")
    return fails, cases


# --- 5. what the shipped DPI makes dead -------------------------------------


def check_dead_paths(base: fl.FleshParams) -> int:
    print("\n  [5] paths the shipped DPI kills — asserted from the parsed DPI")
    fails = 0
    if base.use_small_analysis_image != 0:
        print("      FAIL: useSmallAnalysisImage != 0, so 0x104e8360 IS live")
        fails += 1
    print(f"      useSmallAnalysisImage = {base.use_small_analysis_image} "
          f"(params+0x60a9, tested at 0x102704a9): all four 0x104e8360 call")
    print("      sites (0x102704f4 / 0x10270545 / 0x102705c6 / 0x10270606) are")
    print("      under that test and do NOT execute.  The earlier harnesses'")
    print('      "analysis-image construction" gap was partly a dead branch.')
    print("      What DOES run is fcn.102701e0 (clone via the impl vtable+0x1c)")
    print("      and fcn.1014cc20 = IemTImage<T>::IemTImage(const IemImage&),")
    print('      a type-checked handle wrapper whose only failure is the throw')
    print("      \"Can't construct an %s IemTImage from an %s IemImage\"")
    print("      (0x1014ccb5).  Neither touches a pixel.")
    if base.axial_prob <= 0.0:
        print("      FAIL: axialProb <= 0 would make the weight map unbuildable")
        fails += 1
    return fails


# --- 6. deliberate port bugs ------------------------------------------------


def check_teeth(g, pe, base, weight_cases, prepass_cases) -> int:
    print("\n  [6] deliberate port bugs — the harness must catch each one")
    fails = 0
    caught_any = []

    def probe(label: str, caught, total=None, inert_reason: str | None = None):
        nonlocal fails
        n = caught if isinstance(caught, int) else int(bool(caught))
        tail = f"{n}" + (f"/{total}" if total else "")
        if n:
            print(f"      '{label}': caught on {tail} samples")
            caught_any.append(label)
        elif inert_reason:
            print(f"      '{label}': PROVABLY INERT on this path — {inert_reason}")
        else:
            print(f"      '{label}': MISSED\n      FAILED: a deliberate port "
                  f"bug was invisible")
            fails += 1

    # --- weight map mutations, scored against the DLL's own planes
    def score_weight(fn) -> int:
        n = 0
        for rows, cols, dll in weight_cases:
            host = fn(rows, cols, base)
            for a, b in zip(dll, host):
                for u, v in zip(a, b):
                    n += u != v
        return n

    total_w = sum(len(d) * len(d[0]) for _, _, d in weight_cases)

    real_exp = fl.math.exp
    real_sar1 = fl._sar1

    def mut_divide(rows, cols, params):
        """The 'obvious' port: divide by sigma instead of multiplying by 1/sigma."""
        r, c = fl._to_i16(rows), fl._to_i16(cols)
        b_r = fl.flesh_border(r, params.clip_amount)
        b_c = fl.flesh_border(c, params.clip_amount)
        gg = fl.math.sqrt(fl.WEIGHT_LOG_SCALE * fl.math.log(params.axial_prob))
        sx = (1.0 - params.clip_amount) * float(c) / gg
        sy = (1.0 - params.clip_amount) * float(r) / gg
        cx, cy = fl._sar1(c), fl._sar1(r)
        out = []
        for y in range(b_r, r - b_r):
            ny = (float(y) - cy) / sy
            out.append([fl._to_i16(fl._ftol32(fl.WEIGHT_PEAK * fl.math.exp(
                -0.5 * (((float(x) - cx) / sx) ** 2 + ny * ny))))
                for x in range(b_c, c - b_c)])
        return out

    probe("sigma: divide instead of multiply by the reciprocal",
          score_weight(mut_divide), total_w)

    def mut_round(rows, cols, params):
        real = fl._ftol32
        fl._ftol32 = lambda x: ((int(round(x)) + 0x80000000) & 0xFFFFFFFF) - 0x80000000
        try:
            return fl.flesh_weight_map(rows, cols, params)
        finally:
            fl._ftol32 = real

    probe("weight _ftol32 -> round-to-nearest", score_weight(mut_round), total_w)

    def mut_centre(rows, cols, params):
        fl._sar1 = lambda v: (v + 1) >> 1  # centre off by one on odd dims
        try:
            return fl.flesh_weight_map(rows, cols, params)
        finally:
            fl._sar1 = real_sar1

    probe("centre (dim/2) rounded up instead of toward zero",
          score_weight(mut_centre), total_w)

    def mut_peak(rows, cols, params):
        fl.WEIGHT_PEAK = 1024.0
        try:
            return fl.flesh_weight_map(rows, cols, params)
        finally:
            fl.WEIGHT_PEAK = 1000.0

    probe("peak 1000 (0x105a3c18) -> 1024", score_weight(mut_peak), total_w)

    def mut_logscale(rows, cols, params):
        fl.WEIGHT_LOG_SCALE = -2.0
        try:
            return fl.flesh_weight_map(rows, cols, params)
        finally:
            fl.WEIGHT_LOG_SCALE = -8.0

    probe("sqrt(-8 ln p) (0x10596dc0) -> sqrt(-2 ln p)",
          score_weight(mut_logscale), total_w)

    def mut_swap(rows, cols, params):
        return fl.flesh_weight_map(cols, rows, params)

    swapped = 0
    for rows, cols, dll in weight_cases:
        host = mut_swap(rows, cols, base)
        if len(host) != len(dll) or len(host[0]) != len(dll[0]):
            swapped += len(dll) * len(dll[0])
        else:
            swapped += sum(u != v for a, b in zip(dll, host) for u, v in zip(a, b))
    probe("rows/cols swapped (sigma_x <-> sigma_y)", swapped, total_w)

    # --- pad mutations
    rng = Rng(0x77777)
    src = [[rng.between(-900, 900) for _ in range(5)] for _ in range(4)]
    dll_pad = run_dll_pad(g, src, 11, 12)
    n = sum(dll_pad[y][x] != (src[y - fl._sar1(11 - 4)][x - fl._sar1(12 - 5)]
                              if 0 <= y - fl._sar1(11 - 4) < 4
                              and 0 <= x - fl._sar1(12 - 5) < 5 else 0)
            for y in range(11) for x in range(12))
    probe("pad: constant-zero fill instead of replicate", n, 11 * 12)
    off = fl.flesh_pad_replicate(src, 11, 12)
    off = [r[:] for r in off]
    top = fl._sar1(11 - 4) + 1
    shifted = [[src[min(max(y - top, 0), 3)][min(max(x - fl._sar1(12 - 5), 0), 4)]
                for x in range(12)] for y in range(11)]
    probe("pad: offset rounded up instead of toward zero",
          sum(a != b for ra, rb in zip(dll_pad, shifted) for a, b in zip(ra, rb)),
          11 * 12)

    # --- pre-pass / LUT mutations
    planes, luts, host = prepass_cases[0]
    dll_pre = run_dll_prepass(pe, planes, luts, entry=fl.FLESH_PREPASS1_ENTRY,
                              exit_=fl.FLESH_PREPASS1_EXIT, img_slot=0x40)
    tot_pre = sum(len(p) * len(p[0]) for p in planes)
    swapped_luts = fl.flesh_apply_shift_luts(planes, [luts[1], luts[0], luts[2]])
    probe("pre-pass: plane0/plane1 LUTs swapped",
          sum(a != b for pa, pb in zip(dll_pre, swapped_luts)
              for ra, rb in zip(pa, pb) for a, b in zip(ra, rb)), tot_pre)
    negated = fl.flesh_shift_luts([-s for s in ENTRY_TRIPLES[0]])
    probe("shift LUT: lut[i] = clamp(i - shift) instead of clamp(i + shift)",
          sum(a != b for pa, pb in zip(dll_pre,
                                       fl.flesh_apply_shift_luts(planes, negated))
              for ra, rb in zip(pa, pb) for a, b in zip(ra, rb)), tot_pre)
    hi16 = fl.flesh_shift_luts(ENTRY_TRIPLES[0], hi=0x3FFF)
    probe("shift LUT: 14-bit clamp instead of the 12-bit fcn.1026fed0(0xc)",
          sum(a != b for pa, pb in zip(dll_pre,
                                       fl.flesh_apply_shift_luts(planes, hi16))
              for ra, rb in zip(pa, pb) for a, b in zip(ra, rb)), tot_pre)
    lo_one = fl.flesh_shift_luts(ENTRY_TRIPLES[0], lo=1)
    probe("shift LUT: floor 1 instead of 0",
          sum(a != b for pa, pb in zip(dll_pre,
                                       fl.flesh_apply_shift_luts(planes, lo_one))
              for ra, rb in zip(pa, pb) for a, b in zip(ra, rb)), tot_pre,
          inert_reason="the probe planes never reach i + shift <= 0")

    assert fl.math.exp is real_exp and fl._sar1 is real_sar1
    return fails


# --- 7. the forward chain ---------------------------------------------------


def _synthetic_frame(shifts, h=60, w=80, seed=0x51D2):
    """A frame whose flesh region lands on the shipped tables' own peak.

    The three tables peak at ``l = 18, s = 19, t = 14``, i.e.
    ``L = 1626 + 18*189 = 5028``, ``S = -85 + 19*17 = 238``,
    ``T = -600 + 14*30 = -180``, which inverts to ``(1825, 1616, 1587)``.
    That is the value **after** the shift LUT, so the pixels here are that
    minus the shift triple -- which is the point: the detector sees the
    frame as the candidate balance would leave it.
    """
    rng = Rng(seed)
    skin = tuple(v - s for v, s in zip((1825, 1616, 1587), shifts))
    bg = tuple(v - s for v, s in zip((1400, 1500, 1600), shifts))
    planes = [[[0] * w for _ in range(h)] for _ in range(3)]
    for y in range(h):
        for x in range(w):
            dy, dx = y - h / 2.0, x - w / 2.0
            inside = (dy / (h * 0.28)) ** 2 + (dx / (w * 0.22)) ** 2 < 1.0
            for k in range(3):
                planes[k][y][x] = int(skin[k] if inside else bg[k]) + rng.between(-40, 40)
    return planes


def check_forward(base, tabs) -> int:
    """A synthetic end-to-end, so the assembly is exercised as one chain."""
    print("\n  [7] the assembled forward chain (the assembly is TIER 1 since "
          "pakon_flesh_whole_golden.py)")
    fails = 0
    shifts = ENTRY_TRIPLES[0]
    planes = _synthetic_frame(shifts)
    res = fl.flesh_forward_delta(planes, planes, shifts, params=base,
                                 tables=tabs, exposure=0.0, second_prepass=True)
    print(f"      threshold={res['threshold']} fleshCount={res['flesh_count']} "
          f"area={res['area']} Q={res['fraction']:.4f}")
    print(f"      X={res['x']:.0f} (aim {base.flesh_neutral_aim:g})  "
          f"D={res['drive']:.1f}  Delta={res['delta']:+d}")
    if res["flesh_count"] == 0 or res["delta"] == 0:
        print("      FAILED: the synthetic frame sits on the tables' own peak; a")
        print("      zero Delta here means a stage above is not wired together.")
        fails += 1
    lo, hi = min(MEASURED_DELTAS), max(MEASURED_DELTAS)
    print(f"      docs/74 §178 measured Delta in {lo:+d}..{hi:+d} on six real "
          f"frames; this synthetic lands at {res['delta']:+d}.")
    print("      That comparison is still TIER 4: no capture pairs a measured")
    print("      Delta to the frame that produced it.  What is no longer open is")
    print("      the assembly — pakon_flesh_whole_golden.py runs fcn.10270280 as")
    print("      one function and gets the same numbers as this chain, bit for")
    print("      bit.  Feeding the SAME planes as arg3 and arg4 is,")
    print("      however, now known to be what the vendor does on this path:")
    print("      analyzePostBalance pushes the scene's one analysis image twice")
    print("      (0x100fe396/0x100fe397), so both copyToIemImage calls at")
    print("      0x101c9bac / 0x101c9beb copy the same AnsImageData (tier 3).")
    print("      A control: with second_prepass (arg8) FALSE, i.e. the LST image")
    print("      NOT passed through the shift LUTs, the same frame gives")
    off = fl.flesh_forward_delta(planes, planes, shifts, params=base,
                                 tables=tabs, exposure=0.0, second_prepass=False)
    print(f"      threshold={off['threshold']} fleshCount={off['flesh_count']} "
          f"Delta={off['delta']:+d}  — arg8 is NOT a cosmetic switch.")
    return fails


# --- main -------------------------------------------------------------------


def main(argv: list[str]) -> int:
    dll_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_DLL
    if not dll_path.is_file():
        print(f"FAILED: no DLL at {dll_path}")
        return 1
    pe = dll_path.read_bytes()
    md5 = hashlib.md5(pe).hexdigest()
    print(f"  {dll_path.name} md5 {md5}")
    if md5 != fl.PAKONIMAU_MD5:
        print(f"FAILED: expected md5 {fl.PAKONIMAU_MD5}")
        return 1
    dpi_md5 = hashlib.md5(fl.DEFAULT_DPI.read_bytes()).hexdigest()
    print(f"  {fl.DEFAULT_DPI.name} md5 {dpi_md5}")
    if dpi_md5 != fl.FLESH_DPI_DEFAULT_MD5:
        print(f"FAILED: expected DPI md5 {fl.FLESH_DPI_DEFAULT_MD5}")
        return 1
    for name, want in fl.COND_PROB_MD5.items():
        got = hashlib.md5((fl.COND_PROB_DIR / name).read_bytes()).hexdigest()
        if got != want:
            print(f"FAILED: {name} md5 {got}, expected {want}")
            return 1
    print("  condProbTbl-{l,s,t}.tbl md5 OK")

    base = fl.default_params()
    tabs = fl.default_cond_prob_tables(base)
    g = thr.Guest(pe)

    fails = 0
    wf, weight_cases = check_weight_map(g, base)
    fails += wf
    pf, _ = check_pad(g)
    fails += pf
    fails += check_shift_luts(g)
    prf, prepass_cases = check_prepass(pe)
    fails += prf
    fails += check_dead_paths(base)
    fails += check_teeth(g, pe, base, weight_cases, prepass_cases)
    fails += check_forward(base, tabs)

    print("\n  Porting state (pakon_flesh module flags):")
    print(fl.porting_state())

    assert fl.FLESH_WEIGHT_MAP_PORTED
    assert fl.FLESH_PAD_PORTED
    assert fl.FLESH_SHIFT_LUT_PORTED
    assert fl.FLESH_PREPASS_PORTED
    assert fl.FLESH_DETECTOR_PORTED  # pakon_flesh_whole_golden.py
    assert not fl.FLESH_ANALYSIS_IMAGE_PORTED
    assert not fl.FLESH_ADVANCED_PATH_PORTED
    assert not fl.FLESH_3DLUT_PATH_PORTED

    if fails:
        print(f"\nFAILED ({fails})")
        return 1
    print("\nFLESH weight/pre-pass golden: ALL OK (bit-exact on every ported block)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
