#!/usr/bin/env python3
"""Golden-by-transitivity harness for the Go port of dra, the SECOND subsystem
of ``ColorNegativePath::analyzeAutoTone``'s ANALYSIS half.

WHAT IS BEING CHECKED
=====================
``tools/ansel/pipeline/ansdra/`` is a transcription of
``tools/ansel/python-pipeline/pakon_dra.py`` -- ``AnsDraCapabilityImpl::analyze``
(PakonIMAu.dll ``0x1022b530``, the histograms-in overload, which is the shipped
colour-negative path). dra consumes cna's ``LuminanceHist``/``EdgeHist`` and
``ToneScaleLut`` and produces the ``DraLut`` that contrast and toneHelper then
read.

The Python module's own verification, which this harness does NOT restate:
``pakon_dra_golden.py`` drives the REAL DLL under Unicorn for ``rebin``,
``cum_bounds``, ``eff_bounds``, ``keepMidPtLut``, the ``.dpi``/``.ttc`` parsers
and their slope leaf, ``validate_params``, ``alloc``, ``generateLut`` end to end
and the lighting branch. So a pass here plus a pass there is bit-exactness
against the vendor, by transitivity.

Both the ARITHMETIC and the PARAMETER PARSER are checked. The Go side loads the
vendor ``.dpi`` and its six ``.ttc`` files itself, from the same directory the
Python side reads, and emits what it parsed; a field that silently failed to
parse would otherwise look like a correct port of a wrong number.

WHAT THIS HARNESS CANNOT PROVE
==============================
Nothing about toneHelper / contrast / ast / citras-analyze. dra's ``DraLut`` is
an INPUT to those; the 4096-entry ``OutToneLut`` the render applies is built by
contrast. ``AutoToneAnalysisPorted`` stays false until all of them land.

Nor anything about variant A (``0x1022af20``, the no-tone-object overload). It
is ported in ``ansdra.AnalyzeImage`` but is not reached on the colour-negative
path, so no real data exercises it here and this harness makes no claim about
it.

REAL DATA, NOT SYNTHETIC
========================
The three input arrays are the REAL ones cna produced for a real frame from a
real capture, opened through the real production path -- i.e. this harness runs
the real cna first and feeds dra exactly what the real chain would.

Usage
-----
    python3 tools/test_dra_port.py                 # a real 4x decimation
    python3 tools/test_dra_port.py --full          # the whole real frame
    python3 tools/test_dra_port.py --capture captures/scan-....bin
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

sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(PY_DIR))

import pakon_cna as cna  # noqa: E402
import pakon_dra as dra  # noqa: E402
from test_cna_port import (  # noqa: E402
    KIND_DTYPE, default_capture, diff_stage, real_frame, to_cna_image,
)

#: The lighting value every real colour negative takes. `find("lighting")`
#: always MISSES for CN-Enhanced and a miss is DEFINED to yield 0 (Normal) --
#: Unicorn-verified in pakon_dra_golden.check_lighting, not assumed here. It is
#: also what pakon_autotone.AutoToneSubsystems.dra_acquire_with_hist passes.
LIGHTING = dra.LIGHTING_NORMAL


# ---------------------------------------------------------------------------
# the real inputs: cna's own output for a real frame
# ---------------------------------------------------------------------------


def cna_outputs(capture: Path, decimate: int, cache: Path | None):
    """Run the REAL cna on a REAL frame and return what dra is handed."""
    x = real_frame(capture, decimate, cache)
    img, _clipped = to_cna_image(x)
    t0 = time.time()
    with contextlib.redirect_stdout(io.StringIO()):
        res = cna.analyze_to_results(img, cna.default_params())
    print(f"cna               {time.time() - t0:.1f}s, ToneScaleLut "
          f"{min(res.tone_scale_lut)}..{max(res.tone_scale_lut)}, "
          f"nEdge={res.analysis.n_edge}")
    return res


# ---------------------------------------------------------------------------
# the Python reference
# ---------------------------------------------------------------------------


def python_stages(params, lum_hist, edge_hist, tone_lut) -> dict:
    """Every intermediate ``analyze_hist`` builds, split at the compose.

    ``generate_lut`` and ``compose_tone`` are called separately rather than
    through ``analyze_hist``, so the pre-compose curve is observable: composing
    twice, or not at all, would still produce something plausible from the
    outside.
    """
    n_small = dra._s16(int(params["maxValue"])) + 1
    results = dra.alloc(n_small, lum_hist is not None, edge_hist is not None,
                        int(params["binFactor"]))
    if lum_hist is not None:
        results.LumHist = list(lum_hist)
    if edge_hist is not None:
        results.EdgeHist = list(edge_hist)
    pre = dra.generate_lut(results, params, LIGHTING, tone_lut)
    final = (dra.compose_tone(pre, tone_lut, n_small)
             if tone_lut is not None else pre)

    low, high = params.curve_pair(LIGHTING)
    s = {
        "params_i": np.asarray([
            int(params["maxValue"]), int(params["lowFixedPoint"]),
            int(params["highFixedPoint"]), int(params["paperMin"]),
            int(params["paperMax"]), int(params["binFactor"]),
            int(bool(params["bDoAverage"])), int(bool(params["bIsBacklit"])),
            int(bool(params["bIsFlash"])), dra.validate_params(params),
        ], dtype=np.int64),
        "params_f": np.asarray([
            params["minSlope"], params["maxSlope"], params["lumWeighting"],
            params["edgeWeighting"], params["flashFraction"],
            params["backlitFraction"], params["startingMinCumPoint"],
            params["cumPctBelowMin"], params["startingMaxCumPoint"],
            params["cumPctAboveMax"],
        ], dtype=np.float64),
        "low_x": np.asarray(low.x, dtype=np.float64),
        "low_y": np.asarray(low.y, dtype=np.float64),
        "low_slope": np.asarray(low.slope, dtype=np.float64),
        "high_x": np.asarray(high.x, dtype=np.float64),
        "high_y": np.asarray(high.y, dtype=np.float64),
        "high_slope": np.asarray(high.slope, dtype=np.float64),
        "lum_remapped": np.asarray(results.LumHist or [], dtype=np.int64),
        "lum_large": np.asarray(results.LumLargeHist or [], dtype=np.int64),
        "lum_cum": np.asarray(results.LumCumHist or [], dtype=np.int64),
        "edge_remapped": np.asarray(results.EdgeHist or [], dtype=np.int64),
        "edge_large": np.asarray(results.EdgeLargeHist or [], dtype=np.int64),
        "edge_cum": np.asarray(results.EdgeCumHist or [], dtype=np.int64),
        "bounds": np.asarray([
            results.nSmallBins, results.nLargeBins, results.nLumPixels,
            results.nEdgePixels, results.lumMin, results.lumMax,
            results.edgeMin, results.edgeMax, results.effMin, results.effMax,
        ], dtype=np.int64),
        "lut_precompose": np.asarray(pre, dtype=np.int64),
        "dra_lut": np.asarray(final, dtype=np.int64),
    }
    return s, results


# ---------------------------------------------------------------------------
# the Go side
# ---------------------------------------------------------------------------


def go_stages(exe: Path, dpi_dir: Path, n_small: int, lum_hist, edge_hist,
              tone_lut) -> dict:
    d = str(dpi_dir).encode()
    blob = struct.pack("<6i", n_small, LIGHTING,
                       1 if lum_hist is not None else 0,
                       1 if edge_hist is not None else 0,
                       1 if tone_lut is not None else 0, len(d)) + d
    if lum_hist is not None:
        blob += np.asarray(lum_hist, dtype="<i4").tobytes()
    if edge_hist is not None:
        blob += np.asarray(edge_hist, dtype="<i4").tobytes()
    if tone_lut is not None:
        blob += np.asarray(tone_lut, dtype="<i2").tobytes()

    proc = subprocess.run([str(exe)], input=blob, capture_output=True, cwd=GO_DIR)
    if proc.returncode != 0:
        raise SystemExit(f"dradump failed ({proc.returncode}): "
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


# ---------------------------------------------------------------------------
# negative controls
# ---------------------------------------------------------------------------


def teeth(go: dict, params, lum_hist, edge_hist, tone_lut, results) -> int:
    """Deliberate wrong choices, each checked to be CAUGHT, with the same
    inert-vs-not-caught distinction ``test_cna_port.teeth`` makes and for the
    same reason."""
    print("\nnegative controls (each SHOULD differ — the harness must catch it)")
    failures = 0
    n_small = dra._s16(int(params["maxValue"])) + 1
    in_paper = (int(params["paperMin"]) <= results.effMin
                and results.effMax <= int(params["paperMax"]))

    def control(label: str, patch: dict, stages: tuple[str, ...],
                inert: str | None = None) -> None:
        nonlocal failures
        saved = {k: getattr(dra, k) for k in patch}
        for k, v in patch.items():
            setattr(dra, k, v)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                got, _res = python_stages(params, lum_hist, edge_hist, tone_lut)
            err = None
        except Exception as exc:                       # noqa: BLE001
            got, err = {}, exc
        finally:
            for k, v in saved.items():
                setattr(dra, k, v)
        if err is not None:
            print(f"  {label:<40} raised {type(err).__name__:<18} OK (caught)")
            return
        d, size = 0, 0
        for st in stages:
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

    # 1. cum_bounds returning LARGE-bin indices, i.e. forgetting the final
    #    `imul dx, cx` against binFactor (0x10228c65/0x10228cb2) that converts
    #    back to small-bin units. The two unit systems differ by a factor of 4
    #    with the shipped params and nothing downstream would complain.
    #
    #    A NEARBY CONTROL WAS TRIED AND DISCARDED, and saying so is worth more
    #    than a passing line: the 0.01 at 0x1059f5f0 replaced by the exact
    #    decimal. The two differ by ~2e-10 relative; the thresholds are
    #    `trunc(total * pct * 0.01 + 0.5)` and a real total would have to land
    #    within ~1e-7 of a .5 boundary for that to change an integer. Measured
    #    on this frame: 0 of 8,202 compared values moved. So the vendor's
    #    float32 constant is, here, unobservable — a port that used 0.01 would
    #    pass this harness.
    real_cum = dra.cum_bounds

    def cum_large_units(cum_hist, large_hist, n_large, total, p):
        lo, hi = real_cum(cum_hist, large_hist, n_large, total, p)
        bf = int(p["binFactor"])
        return dra._s16(lo // bf), dra._s16(hi // bf)

    control("cum_bounds: large-bin units, no binFactor",
            {"cum_bounds": cum_large_units},
            ("bounds", "lut_precompose", "dra_lut"))

    # 2. _ftol_round losing the vendor's `fadd 0.5` and becoming a plain
    #    __ftol truncation.
    #
    #    ALSO TRIED AND DISCARDED: round() instead of trunc(x+0.5). Those two
    #    differ only on an exact .5 or a negative argument, and neither occurs
    #    in dra's thresholds or its curve evaluation on real data — 0 of 8,202
    #    values moved. Recorded because it means this harness cannot tell the
    #    vendor's rounding DIRECTION from Python's, only that a bias exists.
    control("_ftol_round: trunc(x), the +0.5 dropped",
            {"_ftol_round": lambda x: int(x)},
            ("bounds", "lut_precompose", "dra_lut"))

    # 3. eff_bounds with the min/max weight split made symmetric. The
    #    asymmetry (min: the SMALLER of a,b keeps its weight; max: the LARGER
    #    does) is the least guessable thing in this file, and "surely they
    #    mirror" is the obvious wrong assumption. Mutating the MIN side, which
    #    is the side whose paper bound really does fall between lum and edge on
    #    real frames.
    real_eff = dra.eff_bounds

    def eff_symmetric(lum_min, lum_max, edge_min, edge_max, paper_min,
                      paper_max, lw, ew, do_average):
        lo, hi = real_eff(lum_min, lum_max, edge_min, edge_max, paper_min,
                          paper_max, lw, ew, do_average)
        if not do_average:
            return lo, hi
        a, b, p = dra._s16(lum_min), dra._s16(edge_min), dra._s16(paper_min)
        if (a - p) * (b - p) >= 0:
            r = a * lw + b * ew
        elif a < b:
            r = b * ew + p * lw          # the mirrored (wrong) split
        else:
            r = a * lw + p * ew
        return dra._s16(dra._ftol_round(r)), hi

    a_, b_, p_ = results.lumMin, results.edgeMin, int(params["paperMin"])
    min_split_live = bool(params["bDoAverage"]) and (a_ - p_) * (b_ - p_) < 0
    control("eff_bounds: symmetric min/max weights",
            {"eff_bounds": eff_symmetric},
            ("bounds", "lut_precompose", "dra_lut"),
            inert=None if min_split_live else
            "paperMin does not fall between lumMin and edgeMin on this frame, "
            "so the MIN blend takes its first (symmetric) arm and the split "
            "the mutation changes is never evaluated")

    # 4. the .ttc slope array left unbuilt. keepMidPtLut only READS this third
    #    array; a port that parsed x/y from the file and stopped there — the
    #    previous state of the Python module — is silently incomplete. The
    #    curves are already parsed by now, so the mutation is applied to the
    #    loaded params object, not to the parser.
    saved_curves = {k: (v.slope, list(v.slope)) for k, v in params.curves.items()}
    for c in params.curves.values():
        c.slope = [0.0] * len(c.slope)
    try:
        control("ttc: slopes all zero", {}, ("lut_precompose", "dra_lut"),
                inert="the effective range lies inside [paperMin, paperMax] "
                      "on this frame, so neither curve is ever evaluated"
                      if in_paper else None)
    finally:
        for k, (orig, _copy) in saved_curves.items():
            params.curves[k].slope = orig

    # 5. compose_tone dropped. generateLut's remap and the post-return compose
    #    are two different uses of the same array; doing only the first is the
    #    natural misreading.
    control("compose: generateLut's remap only",
            {"compose_tone": lambda lut, tone, n: list(lut)},
            ("dra_lut",),
            inert="the incoming ToneScaleLut is the identity over the bins "
                  "this frame occupies, so composing with it is a no-op"
                  if _tone_is_identity(tone_lut, n_small) else None)

    # 6. remap_hist dropped -- the histogram-side counterpart. Same confusion,
    #    opposite half.
    control("remap: skipped inside generateLut",
            {"remap_hist": lambda hist, tone, n: list(hist)},
            ("lum_remapped", "edge_remapped", "lum_large", "bounds",
             "dra_lut"),
            inert="the incoming ToneScaleLut is the identity, so remapping "
                  "through it is a no-op"
                  if _tone_is_identity(tone_lut, n_small) else None)

    # 7. rebin without the int32 narrowing on the running sum.
    control("rebin: no int32 wrap on the sum",
            {"rebin": _rebin_wide},
            ("lum_large", "edge_large", "bounds", "dra_lut"),
            inert="no large-bin sum leaves int32 on this frame")

    return failures


def _tone_is_identity(tone_lut, n) -> bool:
    if tone_lut is None:
        return True
    return all(int(tone_lut[i]) == i for i in range(n))


def _rebin_wide(small, n_small, bin_factor):
    n_large = dra._idiv(n_small, bin_factor)
    out, src = [], 0
    for _ in range(max(n_large, 0)):
        acc = small[src]
        src += 1
        if bin_factor > 1:
            for _ in range(bin_factor - 1):
                acc = acc + small[src]
                src += 1
        out.append(acc)
    return out


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

    print("=== Go: tools/ansel/pipeline/ansdra ===")
    print("reference         python-pipeline/pakon_dra.py "
          "(AnsDraCapabilityImpl::analyze, 0x1022b530)")

    res = cna_outputs(capture, 1 if args.full else max(args.decimate, 1),
                      args.cache)
    lum_hist = list(res.luminance_hist)
    edge_hist = list(res.edge_hist)
    tone_lut = list(res.tone_scale_lut)

    params = dra.DraParams.load(dra.VENDOR_DRA_DIR)
    n_small = dra._s16(int(params["maxValue"])) + 1
    if len(tone_lut) != n_small:
        # cna's histSize (5000) and dra's maxValue+1 (4096) are different
        # numbers, and the shell threads the arrays by POINTER -- dra reads
        # only the first maxValue+1 entries of each. Truncating here is what
        # the real 0x1022b873 rep movsd does, not a convenience.
        print(f"note              cna produced {len(tone_lut)}-entry arrays; "
              f"dra reads the first {n_small} (maxValue+1)")
        lum_hist = lum_hist[:n_small]
        edge_hist = edge_hist[:n_small]
        tone_lut = tone_lut[:n_small]

    with tempfile.TemporaryDirectory(prefix="dra_port_") as td:
        exe = Path(td) / "dradump"
        subprocess.run(["go", "build", "-o", str(exe), "./cmd/dradump"],
                       cwd=GO_DIR, check=True)

        t0 = time.time()
        go = go_stages(exe, dra.VENDOR_DRA_DIR, n_small, lum_hist, edge_hist,
                       tone_lut)
        go_secs = time.time() - t0
        t1 = time.time()
        py, results = python_stages(params, lum_hist, edge_hist, tone_lut)
        py_secs = time.time() - t1
        print(f"dra               go {go_secs:.2f}s, python {py_secs:.2f}s\n")

        order = ["params_i", "params_f", "low_x", "low_y", "low_slope",
                 "high_x", "high_y", "high_slope", "lum_remapped", "lum_large",
                 "lum_cum", "edge_remapped", "edge_large", "edge_cum",
                 "bounds", "lut_precompose", "dra_lut"]
        failures, grand = 0, 0
        for name in order:
            if name not in go:
                print(f"  {name:<14} MISSING from the Go record stream")
                failures += 1
                continue
            d, total = diff_stage(name, go[name], py[name])
            failures += 0 if d == 0 else 1
            grand += total

        b = py["bounds"]
        print(f"\nbounds            lum=[{b[4]},{b[5]}] edge=[{b[6]},{b[7]}] "
              f"eff=[{b[8]},{b[9]}]  paper=[{int(params['paperMin'])},"
              f"{int(params['paperMax'])}]")
        lut = py["dra_lut"]
        ident = int((lut == np.arange(lut.size)).all())
        print(f"DraLut            {lut.size} entries, range {int(lut.min())}.."
              f"{int(lut.max())}, identity: {bool(ident)}")

        if not args.no_teeth:
            failures += teeth(go, params, lum_hist, edge_hist, tone_lut,
                              results)

    print()
    if failures:
        print(f"{failures} failure(s)")
        return 1
    print(f"the Go dra port matches pakon_dra.py bit for bit over "
          f"{grand:,} samples on a real frame, params parser included.")
    print("That module is Unicorn-verified against the real PakonIMAu.dll "
          "(pakon_dra_golden.py), so this is bit-exactness against the vendor "
          "by transitivity — for dra's histogram overload ALONE. toneHelper, "
          "contrast, ast and citras-analyze are still not in Go; "
          "AutoToneAnalysisPorted stays false.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
