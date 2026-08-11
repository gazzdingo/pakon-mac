#!/usr/bin/env python3
r"""Golden ``AnsContrastAdjustCapabilityImpl::constrainSlope`` vs PakonIMAu.dll.

WHY THIS IS ITS OWN FILE
========================
``0x101d2eb0`` is the hardest thing in the contrast subsystem to get right and
the only piece with **two real callers**:

* ``0x101d84ee`` — inside ``analyze``, gated on ``bConstrainSlope``.  That path
  is covered end-to-end by ``pakon_contrast_lut_golden.py``.
* ``0x1010a7f0`` — ``AnsContrastAdjustCapability::constrainSlope``, the public
  entry the Shasta-triage path uses.  Nothing on the ``analyzeAutoTone`` chain
  reaches it, but it is the same code, so porting and verifying the function as
  a standalone unit is worth doing once rather than only as a side effect of
  the mode-1 path.

It is also where all of contrast's genuinely delicate float semantics live: a
least-squares regression whose four sums are accumulated in a specific order in
the FPU register file, a division by the *nominal* sample count rather than the
visited one, and a re-integration whose carried offset is round-tripped through
a **float32** store on every flagged sample.  Any of those getting reordered
shifts LUT entries by one count, which is exactly the class of error a
by-eye port produces and a diff catches.

WHAT RUNS FOR REAL
==================
``0x101d2eb0`` itself, in full, plus ``__ftol`` (``0x104ffe44``, real code in
the image).  Nothing inside it is stubbed: it allocates nothing, calls no CRT
and touches no vtable.  The only stubbed thing in the process is the status
assignment at the very end, which is reached through ``0x100065e0`` — a plain
``lock inc`` — and is skipped anyway because the OK sentinel ``[0x106b5bd4]``
is 0 in the shipped image.

The ``Emu`` (PE load, zeroing bump heap, ``FPCW = 0x027f``) is shared with
``pakon_contrast_lut_golden.py``; see that file's docstring for what each stub
is and why none of it is vendor arithmetic.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \
  tools/ansel/python-pipeline/pakon_contrast_slope_golden.py [dll]``
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import pakon_contrast as cx
from pakon_contrast_lut_golden import (
    Emu,
    DEFAULT_DLL,
    PARAMS_OFF,
    RESULTS_OFF,
    build_impl,
    lut_crushed,
    lut_identity,
    lut_noisy,
    lut_steep,
    shipped_params,
)

#: ``AnsContrastAdjustCapability::constrainSlope`` -- the second, Shasta-side
#: caller of ``0x101d2eb0``.  Recorded so the standalone port has a named
#: consumer; this harness drives the Impl entry directly.
CAP_CONSTRAIN_SLOPE = 0x1010A7F0


# ---------------------------------------------------------------------------
# driving the real function
# ---------------------------------------------------------------------------


def run_dll(pe: bytes, p: cx.ContrastParams, in_lut: list, *,
            scene_type: int, x: int) -> dict:
    """``0x101d2eb0(&status, sceneType, x, inLut, outLut)``, ``ret 0x14``."""
    emu = Emu(pe)
    impl = build_impl(emu, p, cx.ContrastResults())
    n = p.lutSize
    in_ptr = emu.alloc(2 * n, struct.pack(f"<{n}h", *in_lut))
    # The vendor always hands it impl+0x1b0 / impl+0x1b4; separate buffers make
    # the aliasing explicit, and the function zeroes outLut itself anyway.
    out_ptr = emu.alloc(2 * n, b"\xAA" * (2 * n))
    sret = emu.alloc(0x10)
    emu.call(cx.CONSTRAIN_SLOPE, [sret, scene_type, x, in_ptr, out_ptr],
             ecx=impl)
    r = impl + RESULTS_OFF
    return {
        "out": emu.shorts(out_ptr, n),
        "in_untouched": emu.shorts(in_ptr, n) == in_lut,
        "lowerMinSlopeLimit": emu.rf32(r + 0x0C),
        "lowerMaxSlopeLimit": emu.rf32(r + 0x10),
        "upperMinSlopeLimit": emu.rf32(r + 0x14),
        "upperMaxSlopeLimit": emu.rf32(r + 0x18),
        "bWasLowerMinLimitReached": bool(emu.ru8(r + 0x1C)),
        "bWasLowerMaxLimitReached": bool(emu.ru8(r + 0x1D)),
        "bWasUpperMinLimitReached": bool(emu.ru8(r + 0x1E)),
        "bWasUpperMaxLimitReached": bool(emu.ru8(r + 0x1F)),
        "status_ok": emu.r32(sret) == 0,
        "params_untouched": bytes(emu.uc.mem_read(impl + PARAMS_OFF, 0x180))
        == p.to_bytes(points_ptr=struct.unpack_from(
            "<I", bytes(emu.uc.mem_read(impl + PARAMS_OFF, 0x180)), 0x60)[0]),
    }


def run_host(p: cx.ContrastParams, in_lut: list, *, scene_type: int,
             x: int) -> dict:
    res = cx.ContrastResults()
    out = [0] * p.lutSize
    src = list(in_lut)
    cx.constrain_slope(p, res, src, out, scene_type, x)
    return {
        "out": out,
        "in_untouched": src == in_lut,
        "lowerMinSlopeLimit": res.lowerMinSlopeLimit,
        "lowerMaxSlopeLimit": res.lowerMaxSlopeLimit,
        "upperMinSlopeLimit": res.upperMinSlopeLimit,
        "upperMaxSlopeLimit": res.upperMaxSlopeLimit,
        "bWasLowerMinLimitReached": res.bWasLowerMinLimitReached,
        "bWasLowerMaxLimitReached": res.bWasLowerMaxLimitReached,
        "bWasUpperMinLimitReached": res.bWasUpperMinLimitReached,
        "bWasUpperMaxLimitReached": res.bWasUpperMaxLimitReached,
        "status_ok": True,
        "params_untouched": True,
    }


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------


def lut_flat(n: int, max_value: int) -> list[int]:
    """Every entry the same -- regression slope 0, so every window flags -1."""
    return [max_value // 2] * n


def lut_zero(n: int, max_value: int) -> list[int]:
    return [0] * n


def lut_max(n: int, max_value: int) -> list[int]:
    return [max_value] * n


def lut_inverted(n: int, max_value: int) -> list[int]:
    """Descending -- every regression slope is negative."""
    return [max_value - min(i, max_value) for i in range(n)]


def lut_staircase(n: int, max_value: int) -> list[int]:
    """Flat treads with sharp risers: alternating under/over-slope windows."""
    step = max(1, n // 32)
    return [min(max_value, (i // step) * step) for i in range(n)]


def lut_toe_only(n: int, max_value: int) -> list[int]:
    """Shallow below the fixed index, correct above -- only the lower pass fires."""
    out = []
    for i in range(n):
        t = i / (n - 1)
        v = t * 0.15 if t < 0.38 else 0.057 + (t - 0.38) * 1.52
        out.append(max(0, min(max_value, int(v * max_value))))
    return out


LUTS = {
    "identity": lut_identity,
    "crushed": lut_crushed,
    "steep": lut_steep,
    "noisy": lut_noisy,
    "flat": lut_flat,
    "zero": lut_zero,
    "max": lut_max,
    "inverted": lut_inverted,
    "staircase": lut_staircase,
    "toe": lut_toe_only,
}


def cases() -> list[tuple[str, cx.ContrastParams, str, int, int]]:
    """``(label, params, lut name, sceneType, x)``."""
    ship = shipped_params()
    out: list[tuple[str, cx.ContrastParams, str, int, int]] = []

    # every input curve against the shipped limits
    for name in LUTS:
        out.append((f"shipped .dpi limits, {name}", ship, name, 3, 1))

    # every band, on a curve that flags in both passes
    for st in range(0, 10):
        out.append((f"band select: sceneType={st}, x=1", ship, "crushed", st, 1))
    for xv in (0, 1, 2, 3):
        out.append((f"band select: sceneType=0, x={xv}", ship, "crushed", 0, xv))

    # window geometry.  The (gran, nSamples) pair drives an integer division
    # whose remainder is split in half and used as the first sample's offset,
    # so non-divisible pairs are the interesting ones.
    for gran, ns in ((20, 5), (8, 4), (7, 3), (32, 8), (13, 5), (5, 5),
                     (3, 2), (64, 3), (1, 1), (25, 4), (100, 7)):
        out.append((f"csGranularity={gran}, csNSamples={ns}",
                    cx.replace(ship, csGranularity=gran, csNSamples=ns),
                    "crushed", 3, 1))

    # index geometry, including the two "skip a whole pass" degenerate cases
    for lo, fx, up, note in (
        (51, 1550, 3999, "shipped"),
        (0, 0, 4000, "fixed at 0 -- no downward pass, no downward re-integration"),
        (0, 4040, 4040, "fixed near the top -- one upward window only"),
        (51, 1550, 1000, "csUpperIndex < csFixedIndex -- upward pass skipped"),
        (2000, 1550, 3999, "csLowerIndex > csFixedIndex -- downward pass skipped"),
        (100, 200, 300, "a narrow band in the middle"),
        (51, 2048, 4060, "fixed at mid-scale"),
        (1, 2, 3, "one window wide"),
    ):
        out.append((f"indices {lo}/{fx}/{up} ({note})",
                    cx.replace(ship, csLowerIndex=lo, csFixedIndex=fx,
                               csUpperIndex=up), "crushed", 3, 1))

    # limit values that force each flag on its own
    wide = [0.0] * 16
    tight = [100.0] * 16
    out.append(("min limits 0 / max limits 100 -- nothing can flag",
                cx.replace(ship, aLowerMinSlope=list(wide),
                           aUpperMinSlope=list(wide),
                           aLowerMaxSlope=list(tight),
                           aUpperMaxSlope=list(tight)), "crushed", 3, 1))
    out.append(("min limits 5.0 -- every window flags -1",
                cx.replace(ship, aLowerMinSlope=[5.0] * 16,
                           aUpperMinSlope=[5.0] * 16), "crushed", 3, 1))
    out.append(("max limits 0.01 -- every window flags +1",
                cx.replace(ship, aLowerMaxSlope=[0.01] * 16,
                           aUpperMaxSlope=[0.01] * 16), "crushed", 3, 1))
    out.append(("min == max == 1.0 exactly (boundary compare)",
                cx.replace(ship, aLowerMinSlope=[1.0] * 16,
                           aUpperMinSlope=[1.0] * 16,
                           aLowerMaxSlope=[1.0] * 16,
                           aUpperMaxSlope=[1.0] * 16), "identity", 3, 1))
    out.append(("negative min limits",
                cx.replace(ship, aLowerMinSlope=[-2.0] * 16,
                           aUpperMinSlope=[-2.0] * 16), "inverted", 3, 1))

    # a smaller LUT, so the fixed index sits at a different fraction of the range
    small = cx.replace(ship, lutSize=256, maxValue=255, csLowerIndex=8,
                       csFixedIndex=100, csUpperIndex=248, csGranularity=8,
                       csNSamples=4)
    for name in ("identity", "crushed", "staircase", "noisy", "toe"):
        out.append((f"lutSize 256/255, {name}", small, name, 3, 1))

    # a lower maxValue than the LUT range, so the re-integration clamp bites
    out.append(("maxValue 2000 with a 4096 LUT (clamp saturates)",
                cx.replace(ship, maxValue=2000), "identity", 3, 1))
    return out


def _diff(a: dict, b: dict) -> list[str]:
    bad = []
    for k in a:
        av, bv = a[k], b.get(k)
        if k == "out":
            if av != bv:
                i = next(j for j in range(len(av)) if av[j] != bv[j])
                bad.append(f"out: first diff at [{i}] dll={av[i]} host={bv[i]} "
                           f"({sum(1 for p, q in zip(av, bv) if p != q)} of "
                           f"{len(av)} differ)")
            continue
        if av != bv:
            bad.append(f"{k}: dll={av!r} host={bv!r}")
    return bad


def main(argv: list[str]) -> int:
    dll = Path(argv[1]) if len(argv) > 1 else DEFAULT_DLL
    if not dll.exists():
        print(f"{dll} not found — run "
              f"'python3 tools/re/reachability.py extract' first")
        return 2
    if not cx.CONTRAST_CONSTRAIN_SLOPE_PORTED:
        raise RuntimeError("CONTRAST_CONSTRAIN_SLOPE_PORTED is False")
    pe = dll.read_bytes()
    bad = 0
    flagged = 0

    # The vendor samples up to csGranularity/csNSamples past csUpperIndex
    # without a bounds check (see constrain_slope_sample_bounds).  Assert the
    # shipped configuration stays inside the LUT, so the matrix below is
    # comparing arithmetic rather than whatever follows the buffer on the heap.
    lo, hi = cx.constrain_slope_sample_bounds(shipped_params())
    ok = 0 <= lo and hi < shipped_params().lutSize
    bad += not ok
    print(f"== sample-index bounds on the shipped .dpi: in_lut[{lo}..{hi}] of "
          f"{shipped_params().lutSize}  {'OK' if ok else 'FAIL (vendor OOB)'} ==")
    print()

    print("== 0x101d2eb0 constrainSlope: host vs DLL ==")
    for label, p, lut_name, scene_type, x in cases():
        in_lut = LUTS[lut_name](p.lutSize, p.maxValue)
        d = run_dll(pe, p, in_lut, scene_type=scene_type, x=x)
        h = run_host(p, in_lut, scene_type=scene_type, x=x)
        problems = _diff(d, h)
        bad += bool(problems)
        flags = "".join(
            c for c, k in (("l", "bWasLowerMinLimitReached"),
                           ("L", "bWasLowerMaxLimitReached"),
                           ("u", "bWasUpperMinLimitReached"),
                           ("U", "bWasUpperMaxLimitReached")) if d[k]) or "-"
        flagged += flags != "-"
        moved = sum(1 for i, v in enumerate(d["out"]) if v != in_lut[i])
        print(f"  {label:<62} flags={flags:<4} moved={moved:>5} "
              f"{'OK' if not problems else 'FAIL ' + '; '.join(problems[:2])}")

    # A pass in which nothing is ever flagged only exercises the re-integration's
    # unflagged branch, so assert that the matrix really does drive the
    # regression/flagging logic rather than sliding past it.
    print()
    print(f"== cases that actually flagged a window: {flagged} of "
          f"{len(cases())} ==")
    if flagged < 10:
        print("  FAIL — too few cases exercise the regression/flag path")
        bad += 1

    if bad:
        print(f"\nFAILED {bad} check(s)")
        return 1
    print("\nALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
