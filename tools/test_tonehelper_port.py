#!/usr/bin/env python3
"""Golden-by-transitivity harness for the Go port of toneHelper, the THIRD
subsystem of ``ColorNegativePath::analyzeAutoTone``'s ANALYSIS half.

WHAT IS BEING CHECKED
=====================
``tools/ansel/pipeline/anstonehelper/`` is a transcription of
``tools/ansel/python-pipeline/pakon_toneHelper.py`` --
``AnsToneHelperCapabilityImpl::analyze`` (PakonIMAu.dll ``0x101dd1b0``, the
histograms-in overload, which is the shipped colour-negative path). toneHelper
takes cna's two histograms and dra's ``DraLut``, computes 29 metrics over them,
walks a decision tree, and publishes ONE integer: ``toneHelperValue``, which
``analyzeAutoTone`` hands to contrast as its ``x`` argument.

The Python module's own verification, which this harness does NOT restate:
``pakon_toneHelper_core_golden.py`` drives the REAL DLL under Unicorn for
``calcWork`` / ``calcDistance`` / ``calcStats`` and the metric producer
``0x101db020``, and ``pakon_toneHelper_tree_golden.py`` for the walker
``0x101db890`` and the tree verifier. So a pass here plus a pass there is
bit-exactness against the vendor, by transitivity.

WHY THE METRICS ARE COMPARED AND NOT JUST THE ANSWER
====================================================
``toneHelperValue`` is 1 or 2. A port that got most of the 29 metrics wrong
would still agree with the reference roughly half the time by chance. All 29
metrics, both metric groups, the parsed params, the parsed tree and the walk
PATH are diffed; the published integer is the last line, not the evidence.

WHAT THIS HARNESS CANNOT PROVE
==============================
Nothing about contrast (which builds the ``OutToneLut`` the render applies),
ast or citras-analyze. ``AutoToneAnalysisPorted`` stays false until they land.

Nor anything about the image-side overload ``0x101dcc50`` and its edge builder
``0x101dbc00``. Neither the Python nor the Go ports them; the shell only calls
that variant when cna produced no edge histogram, which never happens here.

REAL DATA, NOT SYNTHETIC
========================
The three input arrays are the REAL ones the chain produces for a real frame:
cna's ``LuminanceHist``/``EdgeHist`` and dra's composed ``DraLut``, computed by
running the real cna and the real dra first, exactly as ``analyzeAutoTone``
threads them (``0x100fc36a``).

Usage
-----
    python3 tools/test_tonehelper_port.py
    python3 tools/test_tonehelper_port.py --full
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

import pakon_dra as dra  # noqa: E402
import pakon_toneHelper as th  # noqa: E402
from test_cna_port import KIND_DTYPE, default_capture, diff_stage  # noqa: E402
from test_dra_port import LIGHTING, cna_outputs  # noqa: E402

#: ``exposure`` is ``&ctx[0x4bc]`` at the shell's th.acquireHist call site.
#: ``pakon_autotone.AutoToneSubsystems`` passes the AutoToneContext, whose own
#: default is 0.0, and nothing in this integration has another source for a
#: real per-frame exposure -- so 0.0 with a NON-null pointer is the shell's own
#: documented default, not a value invented here.
EXPOSURE = 0.0

#: The real ``AnsHistogram`` class, captured before any negative control
#: replaces ``th.AnsHistogram`` with a subclass -- a mutation that called back
#: through the module attribute would recurse into itself.
_REAL_HISTOGRAM = th.AnsHistogram


def real_inputs(capture: Path, decimate: int, cache: Path | None):
    """Run the REAL cna and the REAL dra and return what toneHelper is handed."""
    cna_res = cna_outputs(capture, decimate, cache)
    params = dra.DraParams.load(dra.VENDOR_DRA_DIR)
    n_small = dra._s16(int(params["maxValue"])) + 1
    lum = list(cna_res.luminance_hist)[:n_small]
    edge = list(cna_res.edge_hist)[:n_small]
    tone = list(cna_res.tone_scale_lut)[:n_small]
    t0 = time.time()
    with contextlib.redirect_stdout(io.StringIO()):
        dra_res = dra.analyze_hist(params, lum, edge, tone, LIGHTING)
    print(f"dra               {time.time() - t0:.2f}s, DraLut "
          f"{min(dra_res.DraLut)}..{max(dra_res.DraLut)}")
    # The shell threads cna's ORIGINAL histograms to toneHelper (0x100fc36a
    # passes the same lum_hist/edge_hist pointers stage 2 got), and dra's LUT
    # as the tone object -- dra's own remapped copies never leave dra.
    return lum, edge, list(dra_res.DraLut)


def python_stages(p, lum_hist, edge_hist, tone_lut) -> dict:
    res = th.analyze_with_histograms(p, lum_hist, edge_hist, tone_lut, EXPOSURE)
    metrics = th.metrics_by_id(res.lum, res.edge, res.exposure)
    order = ["workLow", "workMidLow", "workSumLow", "workMidHigh", "workHigh",
             "workSumHigh", "workTotal", "distance", "intersection", "average",
             "avgDev", "stdDev", "skew", "kurtosis"]
    nodes_i, nodes_f = [], []
    for nd in p.nodes:
        nodes_i += [nd.metric, nd.less_equal, nd.greater, nd.cls]
        nodes_f.append(nd.threshold)
    walk = th.walk_decision_tree(p.nodes, metrics)
    return {
        "params_i": np.asarray([
            p.maxValue, p.minEdgeThreshold,
            p.lowToneRange[0], p.lowToneRange[1],
            p.midLowToneRange[0], p.midLowToneRange[1],
            p.midHighToneRange[0], p.midHighToneRange[1],
            p.highToneRange[0], p.highToneRange[1],
        ], dtype=np.int64),
        "params_f": np.asarray([
            p.thresholdMultiplier, p.thresholdReductionFactor, p.minEdgeRatio,
            p.smoothingSizeFactor, p.smoothingSigma,
        ], dtype=np.float64),
        "tree_i": np.asarray(nodes_i, dtype=np.int64),
        "tree_f": np.asarray(nodes_f, dtype=np.float64),
        "lum_group": np.asarray([res.lum[k] for k in order], dtype=np.float64),
        "edge_group": np.asarray([res.edge[k] for k in order],
                                 dtype=np.float64),
        "counts": np.asarray([res.lum["count"], res.edge["count"]],
                             dtype=np.int64),
        "metrics": np.asarray([metrics[i] for i in range(2, 31)],
                              dtype=np.float64),
        "path": np.asarray(walk.path, dtype=np.int64),
        "published": np.asarray([res.terminalNode, res.toneHelperValue,
                                 res.sceneClass, res.nPixels], dtype=np.int64),
    }, res


def go_stages(exe: Path, data_dir: Path, lum_hist, edge_hist, tone_lut) -> dict:
    d = str(data_dir).encode()
    blob = struct.pack("<2i", len(lum_hist), 1)
    blob += struct.pack("<d", EXPOSURE)
    blob += struct.pack("<i", len(d)) + d
    blob += np.asarray(lum_hist, dtype="<i4").tobytes()
    blob += np.asarray(edge_hist, dtype="<i4").tobytes()
    blob += np.asarray(tone_lut, dtype="<i2").tobytes()

    proc = subprocess.run([str(exe)], input=blob, capture_output=True, cwd=GO_DIR)
    if proc.returncode != 0:
        raise SystemExit(f"thdump failed ({proc.returncode}): "
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


def teeth(go: dict, p, lum_hist, edge_hist, tone_lut) -> int:
    """Deliberate wrong choices, each checked to be CAUGHT, with the same
    inert-vs-not-caught distinction ``test_cna_port.teeth`` makes."""
    print("\nnegative controls (each SHOULD differ — the harness must catch it)")
    failures = 0

    def control(label: str, patch: dict, stages: tuple[str, ...],
                inert: str | None = None) -> None:
        nonlocal failures
        saved = {k: getattr(th, k) for k in patch}
        for k, v in patch.items():
            setattr(th, k, v)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                got, _res = python_stages(p, lum_hist, edge_hist, tone_lut)
            err = None
        except Exception as exc:                       # noqa: BLE001
            got, err = {}, exc
        finally:
            for k, v in saved.items():
                setattr(th, k, v)
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

    # 1. compute_metrics' `scale2` taken from the calcWork total instead of
    #    calcStats' own count. There are two different counts in scope at
    #    0x101db596 and the code reloads `[esi]` (calcStats' out-parameter),
    #    not EBP; picking the one that is already in a register is the natural
    #    error and it rescales distance and intersection wholesale.
    #
    #    A NEARBY CONTROL WAS TRIED AND DISCARDED, and saying so is worth more
    #    than a passing line: workSumHigh built from the UNROUNDED products,
    #    like workSumLow. The vendor's asymmetry there is real (0x101db50a adds
    #    what is still on the FPU stack; 0x101db4f5/0x101db500 reload the
    #    float32 spills) but it is a sub-ulp choice: measured on this frame,
    #    BOTH the decimated and the full-resolution extent, 0 of 63 compared
    #    values moved. So this harness CANNOT prove the port got that
    #    asymmetry right; it is carried on the Python module's own Unicorn
    #    verification alone.
    real_metrics = th.compute_metrics

    def metrics_wrong_scale2(prm, lum, edge, lut):
        n_bins = prm.maxValue + 1
        scratch = th.AnsHistogram(n_bins, [0] * n_bins, 0, prm.maxValue)
        out = []
        for bins in (lum, edge):
            h = th.AnsHistogram(n_bins, list(bins), 0, prm.maxValue)
            g = {}
            (g["count"], g["average"], g["avgDev"], g["stdDev"], g["skew"],
             g["kurtosis"]) = h.calc_stats(0, 0)
            c_low, w_low = h.calc_work(lut, *prm.lowToneRange)
            c_mlo, w_mlo = h.calc_work(lut, *prm.midLowToneRange)
            c_mhi, w_mhi = h.calc_work(lut, *prm.midHighToneRange)
            c_hi, w_hi = h.calc_work(lut, *prm.highToneRange)
            total = th._i32(c_low + c_mlo + c_mhi + c_hi)
            scale = th._x87_div(th.f32(1.0), float(total))
            e_low, e_mlo = scale * w_low, scale * w_mlo
            e_mhi, e_hi = scale * w_mhi, scale * w_hi
            g["workLow"], g["workMidLow"] = th.f32(e_low), th.f32(e_mlo)
            g["workMidHigh"], g["workHigh"] = th.f32(e_mhi), th.f32(e_hi)
            sum_low = e_low + e_mlo
            g["workSumLow"] = th.f32(sum_low)
            sum_high = g["workMidHigh"] + g["workHigh"]
            g["workSumHigh"] = th.f32(sum_high)
            g["workTotal"] = th.f32(sum_high + sum_low)
            dist, inter = h.calc_distance(lut, scratch, 0, 0)
            scale2 = th._x87_div(th.f32(1.0), float(total))   # the wrong count
            g["distance"] = th.f32(scale2 * dist)
            g["intersection"] = th.f32(scale2 * inter)
            out.append(g)
        return out[0], out[1]

    counts_differ = False
    for bins in (lum_hist, edge_hist):
        h = _REAL_HISTOGRAM(p.maxValue + 1, list(bins), 0, p.maxValue)
        band_total = 0
        for band in ("low", "midLow", "midHigh", "high"):
            c, _w = h.calc_work(tone_lut, *getattr(p, band + "ToneRange"))
            band_total += c
        if h.calc_stats(0, 0)[0] != band_total:
            counts_differ = True
    control("metrics: scale2 from the calcWork total",
            {"compute_metrics": metrics_wrong_scale2},
            ("lum_group", "edge_group", "metrics", "path", "published"),
            inert=None if counts_differ else
            "calcStats' count and the four-band calcWork total are the SAME "
            "number on this frame (every pixel lands inside 600..2449), so the "
            "two candidate divisors are equal and the confusion is invisible")

    # 1b. calcStats' variance as a POPULATION variance (divide by count) rather
    #     than the sample variance the DLL computes (0x10278d1e divides M2 by
    #     count-1). stdDev, skew and kurtosis all hang off it.
    control("calcStats: population variance (/count)",
            {"AnsHistogram": _patched_hist(_stats_pop)},
            ("lum_group", "edge_group", "metrics", "path", "published"))

    # 2. calcStats' moment loop summed in one clean pass, without the
    #    four-slot spill pattern. skew and kurtosis are where it shows.
    real_stats = th.AnsHistogram.calc_stats

    def stats_clean(self, frm, to):
        saved = th.f32
        try:
            th.f32 = lambda v: float(v)
            return real_stats(self, frm, to)
        finally:
            th.f32 = saved

    control("calcStats: no float32 narrowing",
            {"AnsHistogram": _patched_hist(stats_clean)},
            ("lum_group", "edge_group", "metrics", "path", "published"))

    # 3. the walker sending EQUALITY to lessEqual, which is what the file's own
    #    column name says and what the assembly says it is not (0x101dbada's
    #    `test ah,5; jp` takes `greater` on metric >= threshold).
    def walk_le_on_equal(nodes, metrics):
        th.verify_decision_tree(nodes)
        st0, i, path = 0.0, 0, []
        for _ in range(4 * len(nodes) + 8):
            path.append(i)
            nd = nodes[i]
            if nd.metric == th.METRIC_TERMINAL:
                if nd.cls >= 3:
                    return th.TreeWalkResult(i, 2, 3, tuple(path))
                return th.TreeWalkResult(i, 1, nd.cls, tuple(path))
            if 2 <= nd.metric <= 30:
                st0 = metrics[nd.metric]
            i = nd.greater if st0 > nd.threshold else nd.less_equal
        raise th.ToneHelperError("walk did not terminate")

    control("walker: equality goes to lessEqual",
            {"walk_decision_tree": walk_le_on_equal},
            ("path", "published"),
            inert="no node on this frame's path compares exactly equal to its "
                  "threshold, so the two spellings take the same branch "
                  "everywhere it was asked")

    # 4. calcWork reading the tone LUT as UNSIGNED 16-bit. 0x10278f91 is a
    #    `movsx ... word`; a port using an unsigned load only diverges once an
    #    entry has the top bit set, which a 12-bit LUT never does.
    real_work = th.AnsHistogram.calc_work

    def work_unsigned(self, lut, frm, to):
        return real_work(self, [v & 0xFFFF for v in lut], frm, to)

    lut_negative = any(int(v) < 0 for v in tone_lut)
    control("calcWork: unsigned LUT load",
            {"AnsHistogram": _patched_hist_work(work_unsigned)},
            ("lum_group", "edge_group", "metrics", "published"),
            inert=None if lut_negative else
            "no DraLut entry on this frame has its top bit set (the LUT is "
            "12-bit), so signed and unsigned loads agree everywhere")

    # 5. calcDistance's intersection fed on BOTH sides, i.e. made a signed
    #    total. That total is always 0 by construction, so the mutation is
    #    maximally visible and the asymmetry is the whole point of the metric.
    real_dist = th.AnsHistogram.calc_distance

    def dist_signed(self, lut, out, frm, to):
        real_dist(self, lut, out, frm, to)
        frm2, to2 = self._range(frm, to)
        for v in range(frm2, to2 + 1):
            out.bins[v] = 0
        for v in range(frm2, to2 + 1):
            out.bins[th._i16(lut[v])] += self.bins[v]
        dist = inter = 0.0
        for v in range(frm2, to2 + 1):
            d = th._i32(out.bins[v] - self.bins[v])
            dist += abs(float(d))
            inter += float(d)
        return th.f32(dist), th.f32(inter)

    control("calcDistance: signed intersection",
            {"AnsHistogram": _patched_hist_dist(dist_signed)},
            ("lum_group", "edge_group", "metrics", "published"))

    return failures


def _stats_pop(self, frm, to):
    """``calc_stats`` with a POPULATION variance (``M2/count``) instead of the
    sample variance ``0x10278d1e`` computes (``M2/(count-1)``).

    Expressed as the exact rescaling of the real function's own outputs rather
    than as a second copy of the moment loop: ``var_pop = var_samp*(n-1)/n``,
    so ``std``, ``skew`` and ``kurtosis+3`` each scale by a known factor. A
    mutation, not a reimplementation of the reference.
    """
    import math
    count, avg, avgdev, std, skew, kurt = _REAL_HISTOGRAM.calc_stats(
        self, frm, to)
    if count < 2 or std == 0.0:
        return count, avg, avgdev, std, skew, kurt
    ratio = (count - 1) / count                  # var_pop / var_samp
    r = math.sqrt(ratio)                         # std_pop / std_samp
    return (count, avg, avgdev, th.f32(std * r), th.f32(skew / (r * ratio)),
            th.f32((kurt + 3.0) / (ratio * ratio) - 3.0))


def _patched_hist(fn):
    """A subclass of ``AnsHistogram`` with ``calc_stats`` replaced."""
    return type("PatchedStats", (th.AnsHistogram,), {"calc_stats": fn})


def _patched_hist_work(fn):
    return type("PatchedWork", (th.AnsHistogram,), {"calc_work": fn})


def _patched_hist_dist(fn):
    return type("PatchedDist", (th.AnsHistogram,), {"calc_distance": fn})


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

    print("=== Go: tools/ansel/pipeline/anstonehelper ===")
    print("reference         python-pipeline/pakon_toneHelper.py "
          "(AnsToneHelperCapabilityImpl::analyze, 0x101dd1b0)")

    lum_hist, edge_hist, tone_lut = real_inputs(
        capture, 1 if args.full else max(args.decimate, 1), args.cache)

    p = th.load_params()
    n = p.maxValue + 1
    lum_hist = (list(lum_hist[:n]) + [0] * max(0, n - len(lum_hist)))
    edge_hist = (list(edge_hist[:n]) + [0] * max(0, n - len(edge_hist)))
    tone_lut = (list(tone_lut[:n]) + [0] * max(0, n - len(tone_lut)))

    with tempfile.TemporaryDirectory(prefix="th_port_") as td:
        exe = Path(td) / "thdump"
        subprocess.run(["go", "build", "-o", str(exe), "./cmd/thdump"],
                       cwd=GO_DIR, check=True)

        t0 = time.time()
        go = go_stages(exe, th.DATA_DIR, lum_hist, edge_hist, tone_lut)
        go_secs = time.time() - t0
        t1 = time.time()
        py, res = python_stages(p, lum_hist, edge_hist, tone_lut)
        py_secs = time.time() - t1
        print(f"toneHelper        go {go_secs:.2f}s, python {py_secs:.2f}s\n")

        order = ["params_i", "params_f", "tree_i", "tree_f", "lum_group",
                 "edge_group", "counts", "metrics", "path", "published"]
        failures, grand = 0, 0
        for name in order:
            if name not in go:
                print(f"  {name:<12} MISSING from the Go record stream")
                failures += 1
                continue
            d, total = diff_stage(name, go[name], py[name])
            failures += 0 if d == 0 else 1
            grand += total

        print(f"\nwalk              {len(py['path'])} nodes, terminal "
              f"{res.terminalNode}, sceneClass {res.sceneClass}")
        print(f"toneHelperValue   {res.toneHelperValue}   <-- the one integer "
              f"analyzeAutoTone reads (0x100fc5c4), contrast's `x`")

        if not args.no_teeth:
            failures += teeth(go, p, lum_hist, edge_hist, tone_lut)

    print()
    if failures:
        print(f"{failures} failure(s)")
        return 1
    print(f"the Go toneHelper port matches pakon_toneHelper.py bit for bit "
          f"over {grand:,} samples on a real frame, params and decision-tree "
          f"parsers included.")
    print("That module is Unicorn-verified against the real PakonIMAu.dll "
          "(pakon_toneHelper_core_golden.py, pakon_toneHelper_tree_golden.py), "
          "so this is bit-exactness against the vendor by transitivity — for "
          "toneHelper's histogram overload ALONE. contrast, ast and "
          "citras-analyze are still not in Go; AutoToneAnalysisPorted stays "
          "false.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
