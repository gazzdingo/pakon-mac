#!/usr/bin/env python3
"""Golden-by-transitivity harness for the Go port of cna, the FIRST subsystem of
``ColorNegativePath::analyzeAutoTone``'s ANALYSIS half.

WHAT IS BEING CHECKED
=====================
``tools/ansel/pipeline/anscna/`` is a transcription of
``tools/ansel/python-pipeline/pakon_cna.py`` -- ``AnsCnaCapabilityImpl::analyze``
(PakonIMAu.dll ``0x1022ea50``), the subsystem that measures the frame and
produces the ``LuminanceHist`` / ``EdgeHist`` / ``ToneScaleLut`` triple every
later stage of ``analyzeAutoTone`` threads.

The Python module's own verification, which this harness does NOT restate and
does NOT replace: ``pakon_cna_golden.py`` drives the REAL DLL under Unicorn --
``_ftol2``, the laplacian, the gaussian, the peak search, ``hist_resample``,
both contrast-map halves, the LUT builder, the whole of ``0x1022ddc0`` and the
ELMO gate -- and diffs the port against it. So a pass here plus a pass there is
bit-exactness against the vendor, by transitivity.

WHAT THIS HARNESS CANNOT PROVE
==============================
Nothing about the OTHER five subsystems (dra / toneHelper / contrast / ast /
citras-analyze). cna's ``ToneScaleLut`` is an INPUT to dra, not the chain's
output; the 4096-entry ``OutToneLut`` the render actually applies is built by
contrast, three stages downstream. ``AutoToneAnalysisPorted`` stays false until
all of them land -- see ``tools/ansel/pipeline/autotone.go``.

It also cannot prove the two branches where the Go port deliberately diverges
from the Python (a zero histogram total, and an out-of-range luminance reaching
the vendor's unchecked histogram store) -- both are documented at the top of
``anscna.go``, and neither is reachable on the real frames tested here.

REAL DATA, NOT SYNTHETIC
========================
The frame comes from a real capture in ``captures/`` opened through the real
production path (``pakon_render.open_capture`` -> ``_render_colour_python``),
with the post-FUGC RPD-12 array intercepted at ``pakon_ansel.real_auto_tone``'s
own call boundary -- the same interception ``tools/test_citras_driver_ports.py``
uses, and the same array the real chain hands cna. The params are the real
0x7c-byte ``AnsCnaParams`` image, passed over the wire, so the two sides' own
defaults are not trusted.

Usage
-----
    python3 tools/test_cna_port.py                 # a real 4x decimation
    python3 tools/test_cna_port.py --full          # the whole real frame (slow)
    python3 tools/test_cna_port.py --decimate 8
    python3 tools/test_cna_port.py --capture captures/scan-....bin
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
import warnings
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
GO_DIR = REPO / "tools" / "ansel" / "pipeline"
PY_DIR = REPO / "tools" / "ansel" / "python-pipeline"
CAPTURES = REPO / "captures"

sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(PY_DIR))

import pakon_cna as cna  # noqa: E402

#: samples per compare chunk, as in test_citras_driver_ports.py -- diffing in
#: slabs keeps peak RSS bounded and reports the first offending index.
CHUNK = 1 << 22


# ---------------------------------------------------------------------------
# real data
# ---------------------------------------------------------------------------


def default_capture() -> Path:
    """The newest real capture in captures/. Refuses rather than inventing."""
    bins = sorted(CAPTURES.glob("*.bin"))
    if not bins:
        raise SystemExit(
            f"no real capture found in {CAPTURES}. This harness does not "
            "synthesise input -- put a real scan into captures/, or pass "
            "--capture. (Nothing here can be checked against fabricated data; "
            "see CLAUDE.md.)")
    return bins[-1]


def real_frame(capture: Path, decimate: int, cache: Path | None = None
               ) -> np.ndarray:
    """Open a REAL capture through the REAL production path and return the
    post-FUGC RPD-12 array ``real_auto_tone`` is handed.

    ``cache`` re-reads a previously intercepted array instead of re-opening the
    capture (which takes ~100 s for a 2 GB scan). It caches the FULL-resolution
    intercept, before any decimation, so the cached file is the real thing and
    not a harness-specific reduction of it. Off unless asked for.
    """
    if cache is not None and cache.exists():
        x = np.load(cache)
        print(f"real capture      {capture.name} (from cache {cache.name})")
        print(f"post-FUGC RPD-12  {x.shape[0]}x{x.shape[1]}x3")
        return _decimate(x, decimate)

    import pakon_ansel as ansel
    import pakon_render as pr

    captured: dict = {}
    original = ansel.real_auto_tone

    def _intercept(rpd12, scene_type: int = 0):
        captured["x"] = rpd12.copy()
        return rpd12

    ansel.real_auto_tone = _intercept
    t0 = time.time()
    try:
        with tempfile.TemporaryDirectory() as ws, warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with contextlib.redirect_stdout(io.StringIO()):
                roll = pr.open_capture(str(capture), ws, "cna_port",
                                       film_path="ColNeg")
                if not roll.frames:
                    raise SystemExit(f"{capture.name} has no detected frames")
                f = roll.frames[0]
                seg = roll.slice14(f.a, f.b, 1)
                pr._render_colour_python(roll, seg, {})
    finally:
        ansel.real_auto_tone = original
    if "x" not in captured:
        raise SystemExit(
            "real_auto_tone was never called on this capture -- the render "
            "took the stand-in path, so there is no real cna input to compare.")
    x = captured["x"]
    print(f"real capture      {capture.name}")
    print(f"post-FUGC RPD-12  {x.shape[0]}x{x.shape[1]}x3, "
          f"opened in {time.time() - t0:.1f}s")
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.save(cache, x)
    return _decimate(x, decimate)


def _decimate(x: np.ndarray, decimate: int) -> np.ndarray:
    if decimate <= 1:
        return x
    x = x[::decimate, ::decimate]
    print(f"--decimate {decimate:<6} real {decimate}x decimation -> "
          f"{x.shape[0]}x{x.shape[1]} (every value is still one the scanner "
          f"produced)")
    return x


def to_cna_image(x: np.ndarray) -> tuple[cna.CnaImage, np.ndarray]:
    """Exactly what ``real_auto_tone`` builds: clip(rint(x)) as interleaved
    int16, then ``CnaImage``."""
    clipped = np.clip(np.rint(x.astype(np.float64)), -32768, 32767).astype(np.int16)
    h, w = int(clipped.shape[0]), int(clipped.shape[1])
    return cna.CnaImage(width=w, height=h,
                        pixels=clipped.reshape(-1).tolist()), clipped


# ---------------------------------------------------------------------------
# the Python reference
# ---------------------------------------------------------------------------


def python_stages(img: cna.CnaImage, p: cna.CnaParams) -> dict:
    """Every intermediate the real ``pakon_cna`` analysis builds.

    These are pulled out of the module's own ``CnaAnalysis`` rather than
    recomputed here: a harness that reimplements the reference can agree with a
    Go port for the same wrong reason. Only stages the module already exposes
    are compared, which is all of them.
    """
    res = cna.analyze_to_results(img, p)
    a = res.analysis
    st = a.threshold_stage
    s = {
        "lum": np.asarray(st.lum, dtype=np.int16),
        "lum_hist": np.asarray(st.lum_hist, dtype=np.int32),
        "lap": np.asarray(st.lap, dtype=np.int16),
        "lap_hist": np.asarray(st.lap_hist, dtype=np.int32),
        "edge_hist": np.asarray(st.edge_hist, dtype=np.int32),
        "scalars": np.asarray([
            st.n_pixels, st.half, st.peak_index, st.threshold,
            st.min_lap_pixels, st.n_edge, int(bool(st.gave_up)),
            a.pivot, a.pivot_bucket,
        ], dtype=np.int64),
        "bucket_hist": np.asarray(a.bucket_hist, dtype=np.int64),
        "curve": np.asarray(a.curve, dtype=np.float64),
        "tone_lut": np.asarray(res.tone_scale_lut, dtype=np.int16),
        "sigmas": np.asarray([
            a.dark.in_sigma if a.dark else -1.0,
            a.light.in_sigma if a.light else -1.0,
            a.dark.out_sigma if a.dark else -1.0,
            a.light.out_sigma if a.light else -1.0,
            a.elmo.elmo_percent if a.elmo else -1.0,
        ], dtype=np.float64),
        "elmo": np.asarray([
            int(bool(a.elmo.b_elmo_occured)) if a.elmo else 0,
            a.elmo.count if a.elmo else 0,
            int(bool(a.elmo.ran)) if a.elmo else 0,
        ], dtype=np.int64),
        "crosses": np.asarray([a.cross_dark, a.cross_light], dtype=np.int64),
        "percentile": np.asarray([a.percentile], dtype=np.float64),
    }
    if a.dark:
        s["dark_out"] = np.asarray(a.dark.out, dtype=np.int64)
    if a.light:
        s["light_out"] = np.asarray(a.light.out, dtype=np.int64)
    return s, a


# ---------------------------------------------------------------------------
# the Go side
# ---------------------------------------------------------------------------

KIND_DTYPE = {0: np.int16, 1: np.uint8, 2: np.float64, 3: np.int32, 4: np.int64}


def go_stages(exe: Path, clipped: np.ndarray, params: bytes) -> dict:
    """Run cmd/cnadump on the same input and decode its record stream."""
    h, w = int(clipped.shape[0]), int(clipped.shape[1])
    blob = struct.pack("<3i", h, w, len(params)) + params
    blob += np.ascontiguousarray(clipped, dtype="<i2").tobytes()

    proc = subprocess.run([str(exe)], input=blob, capture_output=True, cwd=GO_DIR)
    if proc.returncode != 0:
        raise SystemExit(f"cnadump failed ({proc.returncode}): "
                         f"{proc.stderr.decode(errors='replace')}")
    note = proc.stderr.decode(errors="replace").strip()
    if note:
        print(f"go geometry       {note}")

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
# comparison
# ---------------------------------------------------------------------------


def diff_stage(name: str, mine: np.ndarray, ref: np.ndarray) -> tuple[int, int]:
    """Diff one stage in slabs. Returns (differing samples, total samples).

    Floats are compared by BIT PATTERN, not by ``==``: ``nan != nan`` would
    silently pass a stage whose whole point is that the vendor's NaN cascade
    survives (docs/74 §30), and ``-0.0 == 0.0`` would hide a sign flip.
    """
    mine = np.asarray(mine).reshape(-1)
    ref = np.asarray(ref).reshape(-1)
    if mine.shape != ref.shape:
        print(f"  {name:<12} SHAPE MISMATCH go={mine.shape} py={ref.shape}")
        return max(mine.size, ref.size), max(mine.size, ref.size)
    if mine.dtype.kind == "f":
        mine = mine.view(np.uint64)
        ref = np.asarray(ref, dtype=np.float64).view(np.uint64)
    total = ref.size
    differ, first = 0, -1
    for start in range(0, total, CHUNK):
        a, b = mine[start:start + CHUNK], ref[start:start + CHUNK]
        d = a != b
        if d.any():
            if first < 0:
                first = start + int(np.argmax(d))
            differ += int(d.sum())
    tag = "bit-exact" if differ == 0 else f"FAIL {differ} differ, first at {first}"
    print(f"  {name:<12} {total:>10} samples  {tag}")
    return differ, total


# ---------------------------------------------------------------------------
# negative controls -- does this harness have teeth?
# ---------------------------------------------------------------------------


def teeth(go: dict, img: cna.CnaImage, p: cna.CnaParams,
          analysis) -> int:
    """Deliberate wrong choices, each checked to be CAUGHT.

    Every mutation is a mistake someone transcribing this module would
    plausibly make. Each patches the REAL Python module, re-runs the REAL
    analysis, and diffs the result against Go's own (correct) output.

    A control that does not differ is one of two very different things, and
    this harness distinguishes them rather than printing one word for both:

      * INERT — the harness can PROVE, from the analysis it just ran, that the
        mutation is not a mutation on this data (the branch it changes was
        never taken). Reported with the reason, and not scored as a failure,
        because it is a statement about the frame, not about the port. It is
        also not evidence that the port got that choice right: nothing here
        could tell.
      * NOT CAUGHT — the branch WAS taken and the output is identical anyway,
        i.e. this harness is blind to that class of error. Scored as a failure.
    """
    print("\nnegative controls (each SHOULD differ — the harness must catch it)")
    failures = 0
    go = dict(go)
    #: results.threshold on its own, so a control that only moves that one
    #: published scalar is not diluted by 5,000 unchanged LUT entries.
    go["threshold"] = np.asarray(go["scalars"])[3:4]
    dark, light = analysis.dark, analysis.light
    import math as _math
    nan_cascade = bool(
        (dark and _math.isnan(dark.in_sigma))
        or (light and _math.isnan(light.in_sigma))
        or (dark and not any(dark.out)) or (light and not any(light.out)))
    relaxed = analysis.threshold_stage.reduced_threshold is not None
    elmo_ran = bool(analysis.elmo and analysis.elmo.ran)
    repivoted = analysis.pivot != p.pivot
    lap = analysis.threshold_stage.lap
    lap_wraps = bool(lap) and (max(lap) > 32767 or min(lap) < -32768)

    def control(label: str, patch: dict, stages: tuple[str, ...],
                inert: str | None = None) -> None:
        nonlocal failures
        saved = {k: getattr(cna, k) for k in patch}
        for k, v in patch.items():
            setattr(cna, k, v)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                res = cna.analyze_to_results(img, p)
            a = res.analysis
            got = {
                "lum": np.asarray(a.threshold_stage.lum, dtype=np.int16),
                "lum_hist": np.asarray(a.threshold_stage.lum_hist,
                                       dtype=np.int32),
                "lap": np.asarray(a.threshold_stage.lap, dtype=np.int16),
                "edge_hist": np.asarray(a.threshold_stage.edge_hist,
                                        dtype=np.int32),
                "bucket_hist": np.asarray(a.bucket_hist, dtype=np.int64),
                "dark_out": np.asarray(a.dark.out if a.dark else [],
                                       dtype=np.int64),
                "curve": np.asarray(a.curve, dtype=np.float64),
                "tone_lut": np.asarray(res.tone_scale_lut, dtype=np.int16),
                "threshold": np.asarray([a.threshold], dtype=np.int64),
                "sigmas": np.asarray([
                    a.dark.in_sigma if a.dark else -1.0,
                    a.light.in_sigma if a.light else -1.0,
                    a.dark.out_sigma if a.dark else -1.0,
                    a.light.out_sigma if a.light else -1.0,
                ], dtype=np.float64),
            }
            err = None
        except Exception as exc:                       # noqa: BLE001
            got, err = {}, exc
        finally:
            for k, v in saved.items():
                setattr(cna, k, v)
        if err is not None:
            # A mutation that makes the reference throw is still caught -- the
            # port does not throw. Say which, rather than scoring it silently.
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

    # 1. luminance without the +1. The vendor's `inc eax` on the red term is a
    #    literal bias, not a rounding of the mean; dropping it is the single
    #    easiest misreading of luminance_plane.
    def lum_no_plus_one(image, prm):
        shift = prm.redShift + prm.greenShift + prm.blueShift
        px, n = image.pixels, image.width * image.height
        out = []
        for i in range(n):
            s = px[3 * i] + px[3 * i + 1] + px[3 * i + 2] + shift
            v = cna.idiv(s, 3)
            if shift != 0:
                v = 0 if v < 0 else (cna.K_LUT_MAX if v > cna.K_LUT_MAX else v)
            out.append(cna.i16(v))
        return out

    control("lum: dropped the +1 bias", {"luminance_plane": lum_no_plus_one},
            ("lum", "edge_hist", "tone_lut"))

    # 2. round_half_up losing the vendor's `fadd 0.5` and becoming a plain
    #    _ftol2 truncation. Reading "the vendor calls _ftol2, which truncates"
    #    and stopping there is exactly how this gets dropped.
    #
    #    A NEARBY CONTROL WAS TRIED AND DISCARDED, and saying so is worth more
    #    than a passing line: floor(x+0.5) instead of trunc(x+0.5). Those two
    #    differ only on a NEGATIVE argument, and every site in this subsystem
    #    that can produce one — the resample accumulator `cur`, the descending
    #    contrast map's `acc` — immediately clamps a negative result to 0. So
    #    the vendor's careful truncation direction is UNOBSERVABLE here, and a
    #    port that got it wrong would pass this harness. Measured, not assumed:
    #    0 of 6,000 compared values moved.
    control("rounding: trunc(x), the +0.5 dropped",
            {"round_half_up": cna.ftol2},
            ("bucket_hist", "dark_out", "curve", "tone_lut"))

    # 3. the gaussian's edge policy: zero-pad instead of the vendor's clamp.
    #    0x1022c986/0x1022c9be replicate the end samples; zeroing is the
    #    textbook alternative and the one a transcriber reaches for.
    def gauss_zero_pad(src, n, sigma, ssf):
        d = cna.gauss_half_width(sigma, ssf)
        kern = cna.gauss_kernel(sigma, ssf)
        taps = 2 * d + 1
        pad = [0.0] * d + [cna.f32(v) for v in src[:n]] + [0.0] * d
        out = []
        for b in range(n):
            acc = 0.0
            w = pad[b:b + taps]
            for i in range(taps):
                acc = acc + kern[i] * w[i]
            out.append(cna.f32(acc))
        return out

    control("gauss: zero pad, not edge clamp",
            {"gauss_smooth": gauss_zero_pad},
            ("bucket_hist", "curve", "tone_lut"))

    # 4. the moment loop summed in one clean pass, without the vendor's
    #    float32 spills. 0x1022cab6's unrolled body spills each accumulator to
    #    a dword slot twice per group of four; a transcriber who "simplifies"
    #    that gets a different sigma in the last bits, and sigma drives the
    #    whole resample.
    real_resample = cna.hist_resample

    def resample_clean_moments(params, hist, n, pivot, scale, gain):
        saved = cna.f32
        try:
            # f32 is the only thing the spills do; disabling it inside the
            # moment loop is expressible by disabling it wholesale for the
            # duration of the accumulate, which is what "no spills" means.
            cna.f32 = lambda x: x
            r = real_resample(params, hist, n, pivot, scale, gain)
        finally:
            cna.f32 = saved
        return r

    control("hist_resample: no float32 narrowing",
            {"hist_resample": resample_clean_moments},
            ("sigmas", "dark_out", "curve", "tone_lut"))

    # 5. the histogram walk over the WHOLE image instead of the interior. Both
    #    of 0x1022ddc0's histogram loops skip the one-pixel border, because the
    #    laplacian is only defined there; walking the full plane is the obvious
    #    simplification and is wrong.
    def interior_all(width, height):
        for r in range(height):
            for c in range(width):
                yield r * width + c

    control("histograms: whole plane, not interior",
            {"_interior_indices": interior_all},
            ("lum_hist", "edge_hist", "tone_lut"))

    # 6. build_tone_lut interpolating linearly between buckets. The vendor
    #    advances by curve[j+1]-curve[j] PER BIN, not per bucket -- the
    #    asymmetry looks like a vendor bug and is the most tempting thing in
    #    this file to "fix".
    curve_flat = len(set(analysis.curve)) <= 1
    control("tone LUT: linear bucket interpolation",
            {"build_tone_lut": _lut_linear}, ("tone_lut",),
            inert=None if not curve_flat else
            "the smoothed curve is CONSTANT on this frame (the NaN cascade "
            "pinned every bucket to one value), so curve[j+1]-curve[j] is 0 "
            "and both spellings advance by nothing")

    # 7. the contrast map's low clamp written as `not (ratio >= lo)`. This is
    #    the exact bug docs/74 §30 found and fixed in the Python: for a NaN
    #    ratio the real `test ah,5; jp` SKIPS the clamp, and the `>=` spelling
    #    launders the NaN into a finite lo.
    control("contrast map: NaN-laundering low clamp",
            {"contrast_map_down":
                lambda *a: _map_nan_launder(*a, ascending=False),
             "contrast_map_up":
                lambda *a: _map_nan_launder(*a, ascending=True)},
            ("curve", "tone_lut"),
            inert=None if nan_cascade else
            "no NaN cascade on this frame: both halves' in_sigma are finite "
            "and their resamples are non-empty, so the clamp is never reached "
            "with a NaN")

    # 8. the laplacian widened out of int16. Every intermediate in 0x1022c374
    #    is a 16-bit register, so it wraps; a port using 32-bit arithmetic
    #    diverges only once a value actually leaves int16 range.
    def lap_no_wrap(lum, width, height):
        out = []
        if height <= 2:
            return out
        for r in range(height - 2):
            if width > 2:
                base = (r + 1) * width
                for c in range(1, width - 1):
                    out.append(lum[base + c - 1] - 4 * lum[base + c]
                               + lum[base - width + c] + lum[base + width + c]
                               + lum[base + c + 1])
        return out

    control("laplacian: 32-bit, no int16 wrap",
            {"laplacian": lap_no_wrap}, ("lap", "edge_hist", "tone_lut"),
            inert=None if lap_wraps else
            "no laplacian value leaves int16 on this frame (12-bit luminance "
            "cannot overflow the 16-bit intermediates)")

    # 9. publishing results.threshold AFTER the reduction instead of before.
    #    0x1022e1e6 stores the threshold of the pass that just RAN; the reduced
    #    value belongs to the pass that has not run yet.
    real_thr = cna.analyze_image_threshold

    def threshold_off_by_one(image, prm):
        st = real_thr(image, prm)
        if st.reduced_threshold is not None:
            st.threshold = st.reduced_threshold
        return st

    control("threshold: published after the reduction",
            {"analyze_image_threshold": threshold_off_by_one},
            ("threshold", "tone_lut"),
            inert=None if analysis.threshold_stage.gave_up else
            "the relaxation loop did not bail out, and on the SUCCESS path the "
            "last tried and last reduced thresholds are the same value, so the "
            "two spellings coincide by construction")

    # 10. the ELMO gate as >= instead of >. 0x1022e9a4's `test ah,0x41; jne`
    #     skips the store on equal as well as on less.
    def elmo_ge(params, image, lin, lout):
        r = cna.ElmoResult(elmo_percent=-1.0, b_elmo_occured=False)
        if not (lin > lout) or not (params.elmoCriticalPercent < 100.0):
            return r
        real = cna.elmo_detect
        r = real(params, image, lin, lout)
        r.b_elmo_occured = r.elmo_percent >= params.elmoCriticalPercent
        return r

    control("elmo: >= instead of > at the gate",
            {"elmo_detect": elmo_ge}, ("tone_lut",),
            inert="the ELMO count never ran on this frame "
                  f"(lightInSigma <= lightOutSigma), so bElmoOccured keeps its "
                  f"seed and nothing downstream reads the comparison"
                  if not elmo_ran else
                  "elmoPercent is not exactly equal to elmoCriticalPercent")

    # 11. normalising step 8 at the RE-DERIVED pivot instead of params.pivot.
    #     The vendor keeps the original in its own slot (E-0x04).
    control("normalise at the re-derived pivot",
            {"analyze_image": _analyze_wrong_pivot}, ("tone_lut",),
            inert=None if repivoted else
            "the pivot was not re-derived on this frame (the edge percentile "
            "at params.pivot was already inside [min,max]), so the two pivots "
            "are the same value")

    return failures


def _lut_linear(curve, n_buckets, n_bins):
    """build_tone_lut with the interior advance scaled to bins."""
    lut = [0] * n_bins
    step = cna.idiv(n_bins, n_buckets)
    half = cna.idiv(step, 2)
    pos = half
    for j in range(n_buckets - 1):
        delta = cna.f32(cna.f32(curve[j + 1]) - cna.f32(curve[j])) / step
        acc = cna.f32(curve[j]) * float(step)
        lut[pos] = cna.i16(cna.round_half_up(acc))
        pos += 1
        for _ in range(max(step - 1, 0)):
            acc = acc + delta
            lut[pos] = cna.i16(cna.round_half_up(acc))
            pos += 1
    i = half - 1
    slope = cna.f32(float(lut[i + 2]) - float(lut[i + 1]))
    acc = float(lut[i + 1])
    while i >= 0:
        acc = acc - slope
        if acc < 0.0:
            while i >= 0:
                lut[i] = 0
                i -= 1
            break
        lut[i] = cna.i16(cna.round_half_up(acc))
        i -= 1
    e = n_bins - cna.idiv(step + 1, 2)
    slope = cna.f32(float(lut[e - 1]) - float(lut[e - 2]))
    acc = float(lut[e - 1])
    i = e
    while i < n_bins:
        acc = acc + slope
        if acc > cna.K_TONE_MAX_F32:
            for k in range(i, n_bins):
                lut[k] = cna.K_LUT_MAX
            break
        lut[i] = cna.i16(cna.round_half_up(acc))
        i += 1
    return lut


def _map_nan_launder(params, src, ratio_den, out, pivot, idx, limit, *,
                     ascending):
    """_contrast_map with the low clamp spelled `not (ratio >= lo)`."""
    out[pivot] = cna.f32(float(pivot))
    den = ratio_den[idx]
    ratio = cna.f32(src[pivot]) / cna.f32(den)
    acc = cna.f32(float(idx))
    delta = idx - pivot
    lo, hi = params.lowClamp, params.highClamp
    order = range(pivot + 1, limit) if ascending else range(pivot - 1, -1, -1)
    for i in order:
        if not (ratio >= lo):            # the laundering spelling
            ratio = lo
        elif ratio > hi:
            ratio = hi
        acc = cna.f32(acc + ratio) if ascending else cna.f32(acc - ratio)
        k = cna.round_half_up(acc)
        k = 0 if k < 0 else (limit - 1 if k >= limit else k)
        j = k - delta
        j = 0 if j < 0 else (limit - 1 if j >= limit else j)
        out[i] = cna.f32(float(j))
        den = ratio_den[k]
        ratio = cna.K_ONE_F32 if den == 0.0 else cna.f32(src[i]) / cna.f32(den)


_REAL_ANALYZE_IMAGE = cna.analyze_image


def _analyze_wrong_pivot(image, prm):
    """analyze_image normalising at the re-derived pivot."""
    a = _REAL_ANALYZE_IMAGE(image, prm)
    if a.threshold_stage.gave_up or not a.tone_lut:
        return a
    smoothed = cna.gauss_smooth(a.curve, a.n_buckets,
                                prm.toneScaleSmoothingSigma,
                                prm.smoothingSizeFactor)
    base = cna.build_tone_lut(smoothed, a.n_buckets, prm.histSize)
    delta = a.pivot - base[a.pivot]
    for i in range(prm.histSize):
        v = base[i] + delta
        v = 0 if v < 0 else (cna.K_LUT_MAX if v > cna.K_LUT_MAX else v)
        a.tone_lut[i] = cna.i16(v)
    return a


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true",
                    help="run the whole real frame (minutes in pure Python)")
    ap.add_argument("--decimate", type=int, default=4)
    ap.add_argument("--capture", type=Path, default=None)
    ap.add_argument("--no-teeth", action="store_true")
    ap.add_argument("--cache", type=Path, default=None,
                    help="cache/reuse the full-res intercepted frame (.npy)")
    args = ap.parse_args(argv[1:])

    capture = args.capture or default_capture()
    if not capture.exists():
        raise SystemExit(f"{capture} does not exist")

    print("=== Go: tools/ansel/pipeline/anscna ===")
    print("reference         python-pipeline/pakon_cna.py "
          "(AnsCnaCapabilityImpl::analyze, 0x1022ea50)")

    x = real_frame(capture, 1 if args.full else max(args.decimate, 1),
                   args.cache)
    img, clipped = to_cna_image(x)
    p = cna.default_params()
    params_bytes = cna.params_to_bytes(p)

    with tempfile.TemporaryDirectory(prefix="cna_port_") as td:
        exe = Path(td) / "cnadump"
        subprocess.run(["go", "build", "-o", str(exe), "./cmd/cnadump"],
                       cwd=GO_DIR, check=True)

        t0 = time.time()
        go = go_stages(exe, clipped, params_bytes)
        go_secs = time.time() - t0
        t1 = time.time()
        py, analysis = python_stages(img, p)
        py_secs = time.time() - t1
        print(f"analysis          go {go_secs:.1f}s, python {py_secs:.1f}s\n")

        order = ["lum", "lum_hist", "lap", "lap_hist", "edge_hist", "scalars",
                 "bucket_hist", "dark_out", "light_out", "curve", "tone_lut",
                 "sigmas", "elmo", "crosses", "percentile"]
        failures, grand = 0, 0
        for name in order:
            if name not in py:
                continue
            if name not in go:
                print(f"  {name:<12} MISSING from the Go record stream")
                failures += 1
                continue
            d, total = diff_stage(name, go[name], py[name])
            failures += 0 if d == 0 else 1
            grand += total

        lut = py["tone_lut"]
        print(f"\nToneScaleLut      {lut.size} entries, "
              f"range {int(lut.min())}..{int(lut.max())}, "
              f"identity at pivot {p.pivot}: {int(lut[p.pivot])}")
        sg = py["sigmas"]
        print(f"sigmas            darkIn={sg[0]:g} lightIn={sg[1]:g} "
              f"darkOut={sg[2]:g} lightOut={sg[3]:g} elmo%={sg[4]:g}")
        print(f"threshold stage   threshold={int(py['scalars'][3])} "
              f"nEdge={int(py['scalars'][5])} "
              f"minLapPixels={int(py['scalars'][4])} "
              f"gaveUp={bool(py['scalars'][6])} "
              f"pivot={int(py['scalars'][7])}")

        if not args.no_teeth:
            failures += teeth(go, img, p, analysis)

    print()
    if failures:
        print(f"{failures} failure(s)")
        return 1
    print(f"the Go cna port matches pakon_cna.py bit for bit over "
          f"{grand:,} samples on a real frame.")
    print("That module is Unicorn-verified against the real PakonIMAu.dll "
          "(pakon_cna_golden.py), so this is bit-exactness against the vendor "
          "by transitivity — for cna ALONE. dra, toneHelper, contrast, ast and "
          "citras-analyze are still not in Go; AutoToneAnalysisPorted stays "
          "false.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
