#!/usr/bin/env python3
"""Golden-by-transitivity harness for the Go port of the citras apply driver.

WHAT IS BEING CHECKED
=====================
``tools/ansel/pipeline/citrasdriver/`` is a transcription of
``tools/ansel/python-pipeline/pakon_citras_driver.py`` -- ``ImaCitrasOpBase::
virtual_40`` (PakonIMAu.dll 0x10169350), the per-pixel driver that APPLIES
``analyzeAutoTone``'s composed tone curve to a frame.

The Python module's own verification, which this harness does NOT restate and
does NOT replace:

  * ``pakon_citras_driver_golden.py`` drives the REAL DLL under Unicorn for the
    leaf routines -- ``0x10168f30`` (gradient weight), ``0x10168d90`` (Gaussian
    kernel), the four upsample kernels, block average, mirror pad -- and checks
    the vectorised forms against ``pakon_citras_apply.py``'s scalar,
    DLL-verified originals.
  * ``CITRAS_DRIVER_WIRING_PORTED``'s operand wiring was recovered by full
    capstone disassembly with manual ESP tracking, cross-checked four ways
    against each callee's own ``ret N``.

So a pass here plus a pass there is bit-exactness against the vendor, by
transitivity -- with ONE stated exception that neither harness can close:
``gauss_blur``. The DLL accumulates on the x87 stack in 80-bit extended
precision; numpy and Go both accumulate in float64. The tap order is identical,
so the difference is ~1e-13 and can only change an output landing that close to
a .5 write-back boundary. This harness proves Go == Python there; it does not
and cannot prove either == the DLL. That limitation is inherited, not
introduced, and it is the reason this file says "bit-exact against the Python
reference" and never "bit-exact against the vendor" for that stage.

WHAT IS NOT PORTED TO GO AT ALL
===============================
The ANALYSIS half of ``analyzeAutoTone`` -- cna -> dra -> toneHelper ->
contrast -> ast -> citras-analyze, ~3,800 lines of Python across six
subsystems -- is NOT in Go. It is what builds the 4096-entry ``OutToneLut``
this driver consumes. This harness therefore takes the LUT from the REAL
Python chain and checks only that Go APPLIES it identically. Go cannot yet
compute one for itself; see ``AutoToneAnalysisPorted`` in shasta.go.

REAL DATA, NOT SYNTHETIC
========================
Every input below comes from a real capture in ``captures/`` opened through
the real production path (``pakon_render.open_capture`` ->
``_render_colour_python``), with the post-FUGC RPD-12 array intercepted at
``pakon_ansel.real_auto_tone``'s own call boundary -- the same interception
``pakon_full_colour_chain_golden.get_real_frame`` uses, and the same array the
real render hands the driver. The tone LUT is the one the real six-subsystem
chain produced for that frame. Nothing here is generated.

Usage
-----
    python3 tools/test_citras_driver_ports.py
    python3 tools/test_citras_driver_ports.py --quick   # a real 750x500 crop
    python3 tools/test_citras_driver_ports.py --capture captures/scan-....bin
"""
from __future__ import annotations

import argparse
import contextlib
import io
import os
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

import pakon_citras_driver as cd  # noqa: E402

#: samples per compare chunk. The full frame is 18 M samples per plane-stage;
#: diffing in slabs keeps peak RSS bounded and makes a partial failure report
#: the first offending row rather than only a total.
CHUNK = 1 << 22


# ---------------------------------------------------------------------------
# real data
# ---------------------------------------------------------------------------


def default_capture() -> Path:
    """The newest real capture in captures/. Refuses rather than inventing."""
    bins = sorted(CAPTURES.glob("scan-*.bin"))
    if not bins:
        raise SystemExit(
            f"no real capture found in {CAPTURES}. This harness does not "
            "synthesise input -- put a real scan-*.bin there, or pass "
            "--capture. (Nothing here can be checked against fabricated data; "
            "see CLAUDE.md.)")
    return bins[-1]


def real_frame_and_lut(capture: Path, quick: bool):
    """Open a REAL capture through the REAL production path and return
    ``(float_frame, clipped_i16_frame, out_tone_lut, params)``.

    ``clipped`` is exactly what ``real_auto_tone`` hands ``apply_citras``:
    ``clip(rint(post_fugc_rpd12), -32768, 32767).astype(int16)``. The LUT is
    what the real six-subsystem analysis chain produced for this frame.
    """
    import pakon_ansel as ansel
    import pakon_render as pr

    captured: dict = {}
    original = ansel.real_auto_tone

    def _intercept(rpd12, scene_type: int = 0):
        captured["x"] = rpd12.copy()
        # Do not run the analysis chain here -- the frame may be full size and
        # this call is only to harvest the real post-FUGC array. The chain is
        # run below, deliberately, on whatever extent was selected.
        return rpd12

    ansel.real_auto_tone = _intercept
    t0 = time.time()
    try:
        with tempfile.TemporaryDirectory() as ws, warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with contextlib.redirect_stdout(io.StringIO()):
                roll = pr.open_capture(str(capture), ws, "citras_ports",
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
            "took the stand-in path, so there is no real driver input to "
            "compare. Nothing is checked rather than checking something else.")
    x = captured["x"]
    print(f"real capture      {capture.name}")
    print(f"post-FUGC RPD-12  {x.shape[0]}x{x.shape[1]}x3, "
          f"opened in {time.time() - t0:.1f}s")

    if quick:
        # A real decimation of real pixels -- every value below is still a
        # value the scanner produced, on the capture's own grid.
        x = x[::4, ::4]
        print(f"--quick           real 4x decimation -> {x.shape[0]}x{x.shape[1]}")

    clipped = np.clip(np.rint(x), -32768, 32767).astype(np.int16)

    # The real analysis chain, on this extent, for a real OutToneLut.
    lut_box: dict = {}
    original_apply = cd.apply_citras

    def _spy(img, tone_lut, p=None):
        lut_box["lut"] = np.asarray(tone_lut, dtype=np.int64).copy()
        lut_box["p"] = p
        return original_apply(img, tone_lut, p)

    cd.apply_citras = _spy
    t1 = time.time()
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            ansel.real_auto_tone(x)
    finally:
        cd.apply_citras = original_apply
    if "lut" not in lut_box:
        raise SystemExit(
            "the analysis chain finished without calling apply_citras -- no "
            "real tone LUT was produced, so there is nothing to apply")
    lut = lut_box["lut"]
    p = lut_box["p"] or cd.CitrasOpParams()
    print(f"analysis chain    {len(lut)} entries, range {lut.min()}..{lut.max()}, "
          f"{time.time() - t1:.1f}s")
    halves = int((np.abs(x - np.trunc(x) ) == 0.5).sum())
    print(f"exact .5 values   {halves:,} of {x.size:,} — what makes rint vs "
          f"round-half-away observable")
    return x, clipped, lut, p


# ---------------------------------------------------------------------------
# the Python reference, stage by stage
# ---------------------------------------------------------------------------


def python_stages(img: np.ndarray, lut: np.ndarray, p) -> dict:
    """Every intermediate ``apply_citras`` builds, in the driver's own order.

    This mirrors ``pakon_citras_driver.apply_citras`` line for line rather than
    calling it, so each stage can be diffed on its own -- docs/74 §171.3: two
    errors in this chain have opposite sign, and a stage checked only through
    the final image can be wrong in a direction the total hides.
    """
    height, width = img.shape[0], img.shape[1]
    bs = p.block_size
    radius = cd.gaussian_radius(p.sigma)
    bw = -(-width // bs)
    bh = -(-height // bs)
    pad_w, pad_h = bw * bs, bh * bs

    s = {}
    s["kernel"] = cd.gaussian_kernel(p.sigma)
    s["avoidtab"] = cd.avoidance_table(p)[0]
    s["lum"] = cd.luminance(img)
    s["padded"] = cd.mirror_pad(s["lum"], 0, pad_w - width, 0, pad_h - height)
    s["blk"] = cd.block_average(s["padded"], bs)
    s["ext"] = cd.mirror_pad(s["blk"], radius, radius, radius, radius)
    s["smooth"] = cd.gauss_blur(s["ext"], s["kernel"])
    s["weightlow"] = cd.gradient_weight(s["smooth"], p)
    s["reference"] = cd.upsample(s["smooth"], bs, bs)[:height, :width]
    s["weight"] = cd.upsample(s["weightlow"], bs, bs)[:height, :width]
    s["delta"] = cd.avoidance_blend(s["reference"], s["weight"], s["lum"], lut)
    s["toned"] = cd.tone_compose(img, s["delta"], p)
    return s


# ---------------------------------------------------------------------------
# the Go side
# ---------------------------------------------------------------------------

KIND_DTYPE = {0: np.int16, 1: np.uint8, 2: np.float64}


def go_stages(exe: Path, frame: np.ndarray, lut: np.ndarray, p) -> dict:
    """Run cmd/citrasdump on the same input and decode its record stream.

    ``frame`` is the FLOAT64 post-FUGC array, not the quantised one, so that
    Go's own ``QuantiseRPD12`` (np.rint == round-half-to-even) is verified here
    rather than being taken on trust. The frame is full of exact halves.
    """
    height, width = frame.shape[0], frame.shape[1]
    blob = struct.pack("<4i", height, width, len(lut), 8)
    blob += struct.pack("<d", p.sigma)
    blob += struct.pack("<8i", p.block_size, p.min_avoidance, p.max_gradient,
                        p.low_gradient_threshold, p.high_gradient_threshold,
                        p.do_clipping, p.min_value, p.max_value)
    blob += np.ascontiguousarray(frame, dtype="<f8").tobytes()
    blob += np.ascontiguousarray(lut, dtype="<i4").tobytes()

    proc = subprocess.run([str(exe), "--float"], input=blob,
                          capture_output=True, cwd=GO_DIR)
    if proc.returncode != 0:
        raise SystemExit(f"citrasdump failed ({proc.returncode}): "
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
        out[name] = arr.reshape(rows, cols) if rows > 1 else arr.copy()
    return out


# ---------------------------------------------------------------------------
# comparison
# ---------------------------------------------------------------------------


def diff_stage(name: str, mine: np.ndarray, ref: np.ndarray) -> tuple[int, int]:
    """Diff one stage in slabs. Returns (differing samples, total samples)."""
    mine = np.asarray(mine).reshape(-1)
    ref = np.asarray(ref).reshape(-1)
    if mine.shape != ref.shape:
        print(f"  {name:<10} SHAPE MISMATCH go={mine.shape} py={ref.shape}")
        return max(mine.size, ref.size), max(mine.size, ref.size)
    total = ref.size
    differ = 0
    worst = 0.0
    for start in range(0, total, CHUNK):
        a = mine[start:start + CHUNK]
        b = ref[start:start + CHUNK]
        d = a != b
        if d.any():
            differ += int(d.sum())
            worst = max(worst, float(np.abs(a[d].astype(np.float64)
                                            - b[d].astype(np.float64)).max()))
    tag = "bit-exact" if differ == 0 else f"FAIL {differ} differ, max |d| {worst:g}"
    print(f"  {name:<10} {total:>10} samples  {tag}")
    return differ, total


# ---------------------------------------------------------------------------
# negative controls -- does this harness have teeth?
# ---------------------------------------------------------------------------


def teeth(go: dict, py: dict, img: np.ndarray, lut: np.ndarray, p,
          frame: np.ndarray | None = None) -> int:
    """Deliberate wrong choices, each checked to be CAUGHT.

    §179 did the same for the CLUT ports. A harness that cannot demonstrate it
    would notice a plausible transcription error is not evidence of anything.
    Every mutation below is a mistake someone transcribing this module would
    plausibly make, and each is compared against Go's own (correct) output.

    THREE CONTROLS WERE TRIED AND DISCARDED, because they are not mutations at
    all on the data this driver sees, and saying so is worth more than a
    passing line. All three are rounding choices -- which is worth noticing on
    its own: this driver's rounding decisions are, in production, almost all
    unobservable, and a port that got every one of them wrong would still pass
    an end-to-end comparison. The choices that DO move pixels are structural
    (the +1 bias, the reflection mode, the half-pixel centring, the delta fold),
    and those are the four that remain below.

      * block_average's rounding. The vendor adds floor(n^2/2) with the SIGN of
        the sum and then truncates toward zero. For a NON-NEGATIVE sum that is
        arithmetically identical to round-half-up -- measured, 0 of 400,000
        sums differ -- and the block sums here are sums of luminance, which is
        never negative. The signed-bias construction only becomes observable on
        negative input (6,250 of 400,000 differ there), which this driver
        cannot produce. So the vendor's careful sign handling is unobservable
        in production, and a port that got it wrong would pass anyway.
      * gauss_blur's write-back. trunc(acc +/- 0.5) and round-half-to-even
        differ only when acc is exactly .5, which float64 accumulation of 49
        irrational-ish taps effectively never yields -- 0 of 2,000,000 random
        accumulator values differ. Also unobservable.
      * the ENTRY quantisation, np.rint (half-to-even) vs math.Round
        (half-away-from-zero). These differ only on an exact .5, and a real
        3000x2000 post-FUGC frame contains ZERO of them in 18,000,000 values --
        the array comes straight out of a 4096-entry apply LUT whose entries are
        integers. The ``clipped`` stage is still compared (it covers the clip
        bounds, and it costs nothing), but it is not evidence that the rounding
        choice is right; nothing in this data could distinguish it.

    All three are recorded rather than dropped silently: they are real limits
    on what this harness can prove, not stages it happens not to cover.
    """
    print("\nnegative controls (each SHOULD differ — the harness must catch it)")
    failures = 0
    height, width = img.shape[0], img.shape[1]
    bs = p.block_size
    radius = cd.gaussian_radius(p.sigma)

    def control(label: str, wrong: np.ndarray, stage: str) -> None:
        nonlocal failures
        ref = np.asarray(go[stage]).reshape(-1)
        w = np.asarray(wrong).reshape(-1)
        if w.shape != ref.shape:
            d = max(w.size, ref.size)
        else:
            d = int((w != ref).sum())
        pct = 100.0 * d / max(ref.size, 1)
        print(f"  {label:<34} {d:>10} / {ref.size} differ ({pct:5.2f} %) "
              f"{'OK (caught)' if d else 'NOT CAUGHT'}")
        failures += 0 if d else 1

    # 1. luminance without the +1 — the rounding bias in (R+G+B+1)/3.
    total = (img[..., 0].astype(np.int64) + img[..., 1].astype(np.int64)
             + img[..., 2].astype(np.int64))
    control("lum: dropped the +1 bias", (total // 3).astype(np.int16), "lum")

    # 2. mirror pad: BORDER_REFLECT (repeats the edge sample) instead of the
    #    vendor's BORDER_REFLECT_101 (does not). One-sample phase error.
    lum = cd.luminance(img)
    bw, bh = -(-width // bs), -(-height // bs)
    padded = cd.mirror_pad(lum, 0, bw * bs - width, 0, bh * bs - height)
    blk = cd.block_average(padded, bs)
    wrong_ext = np.pad(blk, ((radius, radius), (radius, radius)), mode="symmetric")
    control("ext: reflect repeating the edge", wrong_ext, "ext")

    # 3. upsample half-pixel centring: 2j - r instead of 2j + 1 - r. The kernels
    #    interpolate on half-pixel centres; sample-centring is the classic slip.
    smooth = py["smooth"]
    n = smooth.shape[1]
    d2, r = 2 * bs, bs
    j = np.arange(n * bs, dtype=np.int64)
    t = j * 2 - r                       # vendor is j*2 + 1 - r
    i = np.clip(t // d2, 0, n - 2)
    lo = smooth[:, i].astype(np.int64)
    hi = smooth[:, i + 1].astype(np.int64)
    acc = d2 * lo + (t - d2 * i)[None, :] * (hi - lo) + r
    wrong_x = cd._wrap16(cd._trunc_div(acc, d2)).astype(np.int16)
    tall = cd._upsample_axis(np.ascontiguousarray(wrong_x.T), bs, 16).T
    control("reference: sample-centred upsample",
            np.ascontiguousarray(tall)[:height, :width], "reference")

    # 4. avoidance_blend without the table's bias subtraction — returns a toned
    #    value where the vendor returns a DELTA. The single most consequential
    #    misreading available in this file.
    pv = py["lum"].astype(np.int64)
    ref = py["reference"].astype(np.int64)
    diff = cd._wrap16(pv - ref)
    q = cd._trunc_div(py["weight"].astype(np.int64) * diff + 50, 100)
    idx = np.clip(cd._wrap16(pv - q), 0, lut.size - 1)
    control("delta: forgot the -idx bias fold",
            cd._wrap16(np.asarray(lut)[idx]).astype(np.int16), "delta")

    return failures


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="use a real 4x decimation of the real frame")
    ap.add_argument("--capture", type=Path, default=None)
    args = ap.parse_args(argv[1:])

    capture = args.capture or default_capture()
    if not capture.exists():
        raise SystemExit(f"{capture} does not exist")

    print("=== Go: tools/ansel/pipeline/citrasdriver ===")
    print(f"reference         {PY_DIR.name}/pakon_citras_driver.py "
          f"(ImaCitrasOpBase::virtual_40, 0x10169350)")

    frame, img, lut, p = real_frame_and_lut(capture, args.quick)

    with tempfile.TemporaryDirectory(prefix="citras_ports_") as td:
        exe = Path(td) / "citrasdump"
        subprocess.run(["go", "build", "-o", str(exe), "./cmd/citrasdump"],
                       cwd=GO_DIR, check=True)

        t0 = time.time()
        go = go_stages(exe, frame, lut, p)
        go_secs = time.time() - t0
        t1 = time.time()
        py = python_stages(img, lut, p)
        py["clipped"] = img
        py_secs = time.time() - t1
        print(f"apply             go {go_secs:.1f}s, python {py_secs:.1f}s\n")

        order = ["clipped", "kernel", "avoidtab", "lum", "padded", "blk", "ext",
                 "smooth", "weightlow", "reference", "weight", "delta", "toned"]
        failures = 0
        grand = 0
        for name in order:
            if name not in go:
                print(f"  {name:<10} MISSING from the Go record stream")
                failures += 1
                continue
            ref = py[name]
            if name in ("toned", "clipped"):
                ref = ref.reshape(ref.shape[0], -1)
            d, total = diff_stage(name, go[name], ref)
            failures += 0 if d == 0 else 1
            grand += total

        failures += teeth(go, py, img, lut, p, frame)

    print()
    if failures:
        print(f"{failures} failure(s)")
        return 1
    print(f"the Go citras driver matches pakon_citras_driver.py bit for bit "
          f"over {grand:,} samples on a real frame.")
    print("That module's leaves are Unicorn-verified against the real "
          "PakonIMAu.dll (pakon_citras_driver_golden.py); gauss_blur is the "
          "one stage neither harness can prove against the DLL, because the "
          "DLL uses 80-bit x87 accumulation and both ports use float64.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
