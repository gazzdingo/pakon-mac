#!/usr/bin/env python3
"""Golden-by-transitivity harness for the Go port of contrast, the FOURTH
subsystem of ``ColorNegativePath::analyzeAutoTone``'s ANALYSIS half -- and the
one that PRODUCES THE OUTPUT.

WHAT IS BEING CHECKED
=====================
``tools/ansel/pipeline/anscontrast/`` is a transcription of
``tools/ansel/python-pipeline/pakon_contrast.py`` --
``AnsContrastAdjustCapabilityImpl`` (PakonIMAu.dll ``0x101d8240`` /
``0x101d8880``). contrast takes dra's ``DraLut`` as its incoming tone curve,
``sceneType`` and toneHelper's ``toneHelperValue`` as ``x``, and produces
``OutToneLut`` -- the 4096-entry curve the render actually applies through the
citras driver. ast and citras-analyze read it afterward but neither writes it
back, so this IS the chain's tone output.

The Python module's own verification, which this harness does NOT restate:
``pakon_contrast_lut_golden.py`` drives the REAL DLL under Unicorn for
``build_ramp`` / ``build_segment`` / the whole ``0x101d8240`` LUT build, and
``pakon_contrast_slope_golden.py`` for ``constrainSlope`` (``0x101d2eb0``) and
its two regression passes. So a pass here plus a pass there is bit-exactness
against the vendor, by transitivity.

WHAT THIS HARNESS CANNOT PROVE
==============================
That the ASSEMBLED four-subsystem Go chain reproduces the vendor's own
``OutToneLut`` end to end. Each subsystem is checked against its own Python
reference on the real inputs the previous stage produced, which is the same
standard ``pakon_ansel.real_auto_tone`` itself meets and no more -- that
function's own docstring is explicit that the assembled chain's
DLL-comparison is a separate, still in-progress verification
(``pakon_autotone_assembled_golden.py``).

It also proves nothing about ``selectParams``/``selectDpi`` (``0x101d5d20``),
which neither port implements: both model the lookup's contract over a
host-side registry, because the real map is built at library initialisation and
only the lookup happens during ``analyzeAutoTone``.

REAL DATA, NOT SYNTHETIC
========================
The incoming tone LUT is the REAL ``DraLut`` for a real frame -- produced by
running the real cna and the real dra first -- and ``x`` is the REAL
``toneHelperValue`` the real toneHelper computed from it, with the shell's own
elmo fork (``0x100fc5cd``) applied. The params are the shipped
``contrast-CNEnhanced.dpi``, parsed independently by both sides.

Usage
-----
    python3 tools/test_contrast_port.py
    python3 tools/test_contrast_port.py --full
"""
from __future__ import annotations

import argparse
import contextlib
import io
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
GO_DIR = REPO / "tools" / "ansel" / "pipeline"
PY_DIR = REPO / "tools" / "ansel" / "python-pipeline"
CONTRAST_DIR = (REPO / "vendor" / "ansel" / "anselinstalldir" / "dataPathItems"
                / "contrast")
DPI_NAME = "contrast-CNEnhanced.dpi"

sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(PY_DIR))

import pakon_contrast as cx  # noqa: E402
import pakon_dra as dra  # noqa: E402
import pakon_toneHelper as th  # noqa: E402
from test_cna_port import KIND_DTYPE, default_capture, diff_stage  # noqa: E402
from test_dra_port import LIGHTING, cna_outputs  # noqa: E402
from test_tonehelper_port import EXPOSURE  # noqa: E402

#: ``ctx+0x44``. ``pakon_autotone.AutoToneContext``'s own default and the one
#: ``pakon_ansel.real_auto_tone`` uses -- this integration has no other source
#: for a real per-frame scene-type classification (a separate, unported
#: capability; docs/64), so 0 is the shell's documented default, not a value
#: invented here.
SCENE_TYPE = 0

#: ``cap+0xe``. ``declareAutoTone`` never sets it, so the real path frees the
#: two intermediates. The harness forces it ON so ``CAdjLut``/``InToneLut`` can
#: be compared; the ``results_i`` record carries the real flag state as well.
KEEP_INTERMEDIATES = True


def real_inputs(capture: Path, decimate: int, cache: Path | None):
    """Run the REAL cna, dra and toneHelper and return contrast's own inputs.

    Returns ``(dra_lut, x, elmo_occured, tone_helper_value)``. ``x`` follows the
    shell's fork at ``0x100fc5cd``: ``elmoAggressiveness`` when cna raised
    ``bElmoOccured``, otherwise ``toneHelperValue``.
    """
    cna_res = cna_outputs(capture, decimate, cache)
    dra_params = dra.DraParams.load(dra.VENDOR_DRA_DIR)
    n_small = dra._s16(int(dra_params["maxValue"])) + 1
    lum = list(cna_res.luminance_hist)[:n_small]
    edge = list(cna_res.edge_hist)[:n_small]
    tone = list(cna_res.tone_scale_lut)[:n_small]
    with contextlib.redirect_stdout(io.StringIO()):
        dra_res = dra.analyze_hist(dra_params, lum, edge, tone, LIGHTING)
    dra_lut = list(dra_res.DraLut)
    print(f"dra               DraLut {min(dra_lut)}..{max(dra_lut)}")

    p_th = th.load_params()
    n_th = p_th.maxValue + 1
    th_res = th.analyze_with_histograms(
        p_th, lum[:n_th], edge[:n_th], dra_lut[:n_th], EXPOSURE)
    elmo = bool(cna_res.analysis.elmo and cna_res.analysis.elmo.b_elmo_occured)
    cna_params = cna_res.analysis  # for elmoAggressiveness, from the params
    x = (int(__import__("pakon_cna").default_params().elmoAggressiveness)
         if elmo else int(th_res.toneHelperValue))
    print(f"toneHelper        toneHelperValue={th_res.toneHelperValue} "
          f"sceneClass={th_res.sceneClass}; bElmoOccured={elmo} -> x={x}")
    del cna_params
    return dra_lut, x, elmo, int(th_res.toneHelperValue)


def python_stages(p, tone_lut, x) -> dict:
    lut_size = p.lutSize
    s: dict = {
        "params_i": np.asarray([
            p.maxValue, p.lutSize, p.userInputMode, p.midpointIn,
            p.midpointOut, int(bool(p.bConstrainSlope)), p.csGranularity,
            p.csNSamples, p.csLowerIndex, p.csFixedIndex, p.csUpperIndex,
            len(p.points),
        ], dtype=np.int64),
        "params_f": np.asarray([
            p.lowInitialSlope, p.highInitialSlope, p.lowIncr, p.highIncr,
            p.allIncr,
        ], dtype=np.float64),
        "slopes": np.asarray(list(p.aLowerMinSlope) + list(p.aLowerMaxSlope)
                             + list(p.aUpperMinSlope) + list(p.aUpperMaxSlope),
                             dtype=np.float64),
        "points": np.asarray([v for pt in p.points for v in pt],
                             dtype=np.int64),
        "band": np.asarray([cx.slope_band(SCENE_TYPE, x)], dtype=np.int64),
    }

    if p.bConstrainSlope and tone_lut is not None:
        in_lut = list(tone_lut[:lut_size])
        cs_out = [0] * lut_size
        r = cx.ContrastResults()
        cx.constrain_slope(p, r, in_lut, cs_out, SCENE_TYPE, x)
        s["cs_lut"] = np.asarray(cs_out, dtype=np.int64)
        s["cs_limits"] = np.asarray([
            r.lowerMinSlopeLimit, r.lowerMaxSlopeLimit,
            r.upperMinSlopeLimit, r.upperMaxSlopeLimit], dtype=np.float64)
        s["cs_flags"] = np.asarray([
            int(r.bWasLowerMinLimitReached), int(r.bWasLowerMaxLimitReached),
            int(r.bWasUpperMinLimitReached), int(r.bWasUpperMaxLimitReached),
        ], dtype=np.int64)

    sub = cx.ContrastSubsystem(p, keep_intermediates=KEEP_INTERMEDIATES)
    sub.acquire(None, SCENE_TYPE, x, tone_lut)
    r = sub.get_results()
    s["results_f"] = np.asarray([
        r.lowSlope, r.highSlope, r.lowerMinSlopeLimit, r.lowerMaxSlopeLimit,
        r.upperMinSlopeLimit, r.upperMaxSlopeLimit], dtype=np.float64)
    s["results_i"] = np.asarray([
        r.lutSize,
        int(r.bWasLowerMinLimitReached), int(r.bWasLowerMaxLimitReached),
        int(r.bWasUpperMinLimitReached), int(r.bWasUpperMaxLimitReached),
        int(r.CAdjLut is not None), int(r.InToneLut is not None),
        int(r.OutToneLut is not None)], dtype=np.int64)
    if r.CAdjLut is not None:
        s["adj_lut"] = np.asarray(r.CAdjLut, dtype=np.int64)
    if r.InToneLut is not None:
        s["in_lut"] = np.asarray(r.InToneLut, dtype=np.int64)
    if r.OutToneLut is not None:
        s["out_tone_lut"] = np.asarray(r.OutToneLut, dtype=np.int64)
    return s, r


def go_stages(exe: Path, lut_size: int, x: int, tone_lut) -> dict:
    d = str(CONTRAST_DIR).encode()
    nm = DPI_NAME.encode()
    blob = struct.pack("<5i", lut_size, SCENE_TYPE, x,
                       1 if KEEP_INTERMEDIATES else 0,
                       1 if tone_lut is not None else 0)
    blob += struct.pack("<i", len(d)) + d
    blob += struct.pack("<i", len(nm)) + nm
    if tone_lut is not None:
        blob += np.asarray(tone_lut, dtype="<i2").tobytes()

    proc = subprocess.run([str(exe)], input=blob, capture_output=True, cwd=GO_DIR)
    if proc.returncode != 0:
        raise SystemExit(f"contrastdump failed ({proc.returncode}): "
                         f"{proc.stderr.decode(errors='replace')}")
    note = proc.stderr.decode(errors="replace").strip()
    if note:
        print(f"go params         {note}")

    out, buf, off = {}, proc.stdout, 0
    while True:
        n = buf[off]
        off += 1
        if n == 0:
            break
        name = buf[off:off + n].decode()
        off += n
        rows, cols = struct.unpack_from("<ii", buf, off)
        off += 8
        elem, kind = buf[off], buf[off + 1]
        off += 2
        count = rows * cols
        arr = np.frombuffer(buf, dtype=KIND_DTYPE[kind], count=count, offset=off)
        off += count * elem
        out[name] = arr.copy()
    return out


def teeth(go: dict, p, tone_lut, x, results) -> int:
    """Deliberate wrong choices, each checked to be CAUGHT, with the same
    inert-vs-not-caught distinction ``test_cna_port.teeth`` makes."""
    print("\nnegative controls (each SHOULD differ — the harness must catch it)")
    failures = 0
    flagged = bool(results.bWasLowerMinLimitReached
                   or results.bWasLowerMaxLimitReached
                   or results.bWasUpperMinLimitReached
                   or results.bWasUpperMaxLimitReached)

    def control(label: str, patch: dict, stages: tuple[str, ...],
                inert: str | None = None, params=None) -> None:
        nonlocal failures
        saved = {k: getattr(cx, k) for k in patch}
        for k, v in patch.items():
            setattr(cx, k, v)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                got, _r = python_stages(params or p, tone_lut, x)
            err = None
        except Exception as exc:                       # noqa: BLE001
            got, err = {}, exc
        finally:
            for k, v in saved.items():
                setattr(cx, k, v)
        if err is not None:
            print(f"  {label:<40} raised {type(err).__name__:<18} OK (caught)")
            return
        d, size = 0, 0
        for st in stages:
            if st not in go or st not in got:
                d += 1
                size += 1
                continue
            ref = np.asarray(go[st]).reshape(-1)
            w = np.asarray(got[st]).reshape(-1)
            if w.dtype.kind == "f":
                w = w.view(np.uint64)
                ref = np.asarray(ref, dtype=np.float64).view(np.uint64)
            if w.shape != ref.shape:
                d += max(w.size, ref.size)
                size += max(w.size, ref.size)
                continue
            d += int((w != ref).sum())
            size += ref.size
        if d == 0 and inert:
            print(f"  {label:<40} {'inert on this frame':>19}  "
                  f"({inert}) — unproven, not failed")
            return
        pct = 100.0 * d / max(size, 1)
        print(f"  {label:<40} {d:>9} / {size} differ ({pct:5.2f} %) "
              f"{'OK (caught)' if d else 'NOT CAUGHT'}")
        failures += 0 if d else 1

    # 1. build_ramp recomputing `mid + i*slope` instead of accumulating by
    #    repeated `fadd slope`. Mathematically the same line; numerically not,
    #    because the vendor's float error accumulates over up to 2545 steps.
    def ramp_recomputed(buf, max_value, mid_in, mid_out, end_index, slope):
        slope = cx._f32(slope)
        buf[mid_in] = mid_out
        if cx._i16(mid_in) == cx._i16(end_index):
            return
        if cx._i16(mid_in) < cx._i16(end_index):
            i, last, base = mid_in, end_index, mid_in
        else:
            i, last, base = end_index, mid_in, mid_in
        for k in range(i, last + 1):
            if k == mid_in:
                continue
            v = float(mid_out) + float(k - base) * slope
            r = cx._ftol16(cx.ROUND_HALF + v)
            buf[k] = 0 if r < 0 else (max_value if r > max_value else r)

    unit_slopes = (results.lowSlope == 1.0 and results.highSlope == 1.0)
    control("build_ramp: recomputed, not accumulated",
            {"build_ramp": ramp_recomputed},
            ("adj_lut", "out_tone_lut"),
            inert=None if not unit_slopes else
            "both slopes are exactly 1.0 on this frame (the shipped .dpi's "
            "initial slopes, unchanged because analyzeAutoTone never calls "
            "changeContrast), so every partial sum is an exact integer and "
            "accumulation cannot drift from recomputation")

    # 1b. build_ramp's DESCENDING seed. 0x101d2b0d starts the downward run at
    #     `(endIndex - midIn - 1)*slope + midOut`, one step past the midpoint
    #     measured from the far end; `midOut - slope` is the symmetric-looking
    #     guess and it shifts the whole low half of the curve.
    real_ramp = cx.build_ramp

    def ramp_wrong_descend_seed(buf, max_value, mid_in, mid_out, end_index,
                                slope):
        if cx._i16(mid_in) <= cx._i16(end_index):
            return real_ramp(buf, max_value, mid_in, mid_out, end_index, slope)
        slope = cx._f32(slope)
        buf[mid_in] = mid_out
        i, last = end_index, mid_in
        val = float(mid_out) - slope          # the wrong seed
        if cx._i16(i) > cx._i16(last):
            return
        max_f = cx._f32(float(max_value))
        while True:
            val = val + slope
            if slope > cx.FZERO and val >= max_f:
                for k in range(i, last + 1):
                    buf[k] = max_value
                return
            if slope < cx.FZERO and val <= cx.FZERO:
                for k in range(i, last + 1):
                    buf[k] = 0
                return
            r = cx._ftol16(cx.ROUND_HALF + val)
            buf[i] = 0 if r < 0 else (max_value if r > max_value else r)
            i += 1
            if cx._i16(i) > cx._i16(last):
                return

    control("build_ramp: descending seed = midOut - slope",
            {"build_ramp": ramp_wrong_descend_seed},
            ("adj_lut", "out_tone_lut"))

    # 2. constrainSlope's re-integration refreshing `offset` at FULL double
    #    precision instead of through the float32 store at 0x101d32b8. One of
    #    the least visible choices in the file and one of the easiest to drop.
    real_cs = cx.constrain_slope

    def cs_no_f32_offset(prm, res, in_lut, out_lut, scene_type, xx):
        saved = cx._f32
        try:
            cx._f32 = lambda v: v
            return real_cs(prm, res, in_lut, out_lut, scene_type, xx)
        finally:
            cx._f32 = saved

    control("constrainSlope: no float32 offset store",
            {"constrain_slope": cs_no_f32_offset},
            ("cs_lut", "out_tone_lut"),
            inert=("no regression window on this frame tripped a slope limit, "
                   "so the re-integration never refreshes `offset` at all"
                   if not flagged else
                   "windows ARE flagged here, so the store executes — but the "
                   "float32 rounding it applies never moves trunc(d + 0.5) "
                   "across an integer boundary: measured, 0 of 8,192. A port "
                   "that dropped this store would pass this harness"))

    # 2b. the two UPPER slope-limit rows swapped. constrainSlope reads four
    #     separate 16-entry arrays at params+0x70/+0xb0/+0xf0/+0x130 and the
    #     min/max pairing is only visible in the compare direction; a
    #     transcription that lined them up wrong changes both the flags and the
    #     slopes the re-integration walks at.
    swapped = cx.replace(p,
                         aUpperMinSlope=list(p.aUpperMaxSlope),
                         aUpperMaxSlope=list(p.aUpperMinSlope))
    control("slope limits: aUpperMin/Max rows swapped", {},
            ("cs_lut", "cs_limits", "cs_flags", "out_tone_lut"),
            params=swapped)

    # 3. the compose reading the RAW incoming LUT rather than the constrained
    #    one. 0x101d85ef picks out_lut when bConstrainSlope ran; using in_lut
    #    unconditionally throws the whole slope constraint away silently.
    real_analyze = cx.ContrastImpl.analyze

    def analyze_wrong_src(self, params, scene_type, xx, tone, keep_intermediates=False):
        r = real_analyze(self, params, scene_type, xx, tone,
                         keep_intermediates=True)
        prm = self.params
        if not prm.bConstrainSlope or r.InToneLut is None or r.CAdjLut is None:
            return r
        if prm.userInputMode not in cx.MODES_COMBINE:
            return r
        out = list(r.OutToneLut)
        for i in range(prm.lutSize):
            out[i] = r.CAdjLut[cx._i16(r.InToneLut[i])]   # the raw source
        r.OutToneLut = out
        if not keep_intermediates:
            r.CAdjLut = None
            r.InToneLut = None
        return r

    control("compose: raw tone LUT, not the constrained one",
            {"ContrastImpl": _patched_impl(analyze_wrong_src)},
            ("out_tone_lut",),
            inert=None if flagged else
            "constrainSlope flagged no window on this frame, so the "
            "constrained curve and the raw one are the same array")

    # 4. the csumpperixedindex typo "fixed". A .dpi that spells csUpperIndex
    #    correctly must be REJECTED; a port that accepts it diverges from the
    #    real scanner. Exercised by parsing a .dpi that sets both spellings to
    #    different values and checking which one won.
    text = (CONTRAST_DIR / DPI_NAME).read_text()
    fixed_typo = cx.parse_dpi(text + "\ncsUpperIndex = 2000\n")
    kept_typo = cx.parse_dpi(text + "\ncsumpperixedindex = 2000\n")
    ok_typo = (fixed_typo.csUpperIndex == 3999 and kept_typo.csUpperIndex == 2000)
    print(f"  {'dpi: csUpperIndex is unsettable':<40} "
          f"correct spelling -> {fixed_typo.csUpperIndex}, "
          f"vendor typo -> {kept_typo.csUpperIndex}  "
          f"{'OK' if ok_typo else 'WRONG'}")
    failures += 0 if ok_typo else 1

    # 5. _ftol16 keeping the full 64-bit result instead of narrowing to ax.
    #    Only observable once a value leaves int16, which the clamps mostly
    #    prevent -- reported honestly either way.
    control("_ftol16: no narrowing to ax",
            {"_ftol16": lambda v: (0 if (v != v or v >= cx._INT64_LIMIT
                                         or v < -cx._INT64_LIMIT) else int(v))},
            ("adj_lut", "cs_lut", "out_tone_lut"),
            inert="every value this frame feeds _ftol16 is already inside "
                  "int16, so the narrowing is a no-op")

    # 6. build_segment's flat-segment fast path made a sloped one. The vendor
    #    rep-stoses a flat segment with no float arithmetic at all.
    real_seg = cx.build_segment

    def seg_no_flat(buf, max_value, a_in, a_out, b_in, b_out):
        if (a_out & 0xFFFF) == (b_out & 0xFFFF) and a_in != b_in:
            b_out = b_out + 1 if b_out < max_value else b_out - 1
        return real_seg(buf, max_value, a_in, a_out, b_in, b_out)

    control("build_segment: flat path perturbed",
            {"build_segment": seg_no_flat}, ("adj_lut", "out_tone_lut"),
            inert="the shipped .dpi's mode is COMBINE_WITH_SLOPE, so "
                  "build_segment is never called on this path")

    return failures


def _patched_impl(fn):
    return type("PatchedImpl", (cx.ContrastImpl,), {"analyze": fn})


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--decimate", type=int, default=4)
    ap.add_argument("--capture", type=Path, default=None)
    ap.add_argument("--no-teeth", action="store_true")
    ap.add_argument("--cache", type=Path, default=None)
    args = ap.parse_args(argv[1:])

    capture = args.capture or default_capture()
    if not capture.exists():
        raise SystemExit(f"{capture} does not exist")

    print("=== Go: tools/ansel/pipeline/anscontrast ===")
    print("reference         python-pipeline/pakon_contrast.py "
          "(AnsContrastAdjustCapabilityImpl, 0x101d8240)")

    tone_lut, x, _elmo, _thv = real_inputs(
        capture, 1 if args.full else max(args.decimate, 1), args.cache)

    p = cx.parse_dpi((CONTRAST_DIR / DPI_NAME).read_text())
    lut_size = p.lutSize
    tone_lut = list(tone_lut[:lut_size]) + [0] * max(0, lut_size - len(tone_lut))

    with tempfile.TemporaryDirectory(prefix="cx_port_") as td:
        exe = Path(td) / "contrastdump"
        subprocess.run(["go", "build", "-o", str(exe), "./cmd/contrastdump"],
                       cwd=GO_DIR, check=True)

        t0 = time.time()
        go = go_stages(exe, lut_size, x, tone_lut)
        go_secs = time.time() - t0
        t1 = time.time()
        py, results = python_stages(p, tone_lut, x)
        py_secs = time.time() - t1
        print(f"contrast          go {go_secs:.2f}s, python {py_secs:.2f}s\n")

        order = ["params_i", "params_f", "slopes", "points", "band", "cs_lut",
                 "cs_limits", "cs_flags", "results_f", "results_i", "adj_lut",
                 "in_lut", "out_tone_lut"]
        failures, grand = 0, 0
        for name in order:
            if name not in py:
                continue
            if name not in go:
                print(f"  {name:<14} MISSING from the Go record stream")
                failures += 1
                continue
            d, total = diff_stage(name, go[name], py[name])
            failures += 0 if d == 0 else 1
            grand += total

        lut = py["out_tone_lut"]
        ident = bool((lut == np.arange(lut.size)).all())
        print(f"\nOutToneLut        {lut.size} entries, range {int(lut.min())}.."
              f"{int(lut.max())}, identity: {ident}")
        print(f"limits reached    lowerMin={bool(py['results_i'][1])} "
              f"lowerMax={bool(py['results_i'][2])} "
              f"upperMin={bool(py['results_i'][3])} "
              f"upperMax={bool(py['results_i'][4])}")

        if not args.no_teeth:
            failures += teeth(go, p, tone_lut, x, results)

    print()
    if failures:
        print(f"{failures} failure(s)")
        return 1
    print(f"the Go contrast port matches pakon_contrast.py bit for bit over "
          f"{grand:,} samples on a real frame, .dpi parser included — "
          f"OutToneLut included.")
    print("That module is Unicorn-verified against the real PakonIMAu.dll "
          "(pakon_contrast_lut_golden.py, pakon_contrast_slope_golden.py), so "
          "this is bit-exactness against the vendor by transitivity — for "
          "contrast ALONE. The ASSEMBLED chain has not been diffed against the "
          "DLL end to end on either side.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
