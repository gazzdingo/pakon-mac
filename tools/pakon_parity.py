#!/usr/bin/env python3
"""Go-vs-Python parity harness for the F-135 colour chain.

    python3 tools/pakon_parity.py

Runs both engines over the same input frame and reports the divergence at
every stage, not just at the end.

WHY IT EXISTS. Until now nothing compared the two implementations of this
chain. There were no ``*_test.go`` files, no comparison script, and the
"within ~2 %" figures in comments and reports were prose about unrelated
round-trips or ad-hoc hand measurements. docs/62 §0 established that; this is
the instrument it said had to be built first. A migration that cannot be
verified is a migration that ships its next divergence the same way it
shipped the last one.

WHY PER-STAGE. A single end-of-chain mean tells you the engines disagree and
nothing about where. These LUTs and clamps compose, so a one-code difference
at stage 2 can be 60 codes after FUGC and invisible after the ICC hop — or the
reverse. The taps are:

    poly     stage 2 polynomial output, linear 12-bit  (TLB fcn.1000d880)
    inv      after the F-135 negative->positive log    (RPD-12)
    balance  after applyBalanceShifts                  (RPD-12)
    shasta   after the Shasta two-anchor tone stand-in (RPD-12)
    fugc     after the FUGC apply LUT                  (RPD-12)
    ansel    the toned RPD-12 handed to the ICC hop
    icc      8-bit sRGB

``shasta`` and ``fugc`` are tapped by NAME, not by position, so the two stage
orders can be compared against each other as well as across engines.

FIXTURES. The default is a synthetic frame from a checked-in generator, not
checked-in data: it is deterministic, it spans the 14-bit input domain far
more evenly than a photograph, and it carries a clear-film region so FindDmin
has something to find. ``--raw`` takes a real (h, w, 3) u16 frame from disk
for local runs. NOTHING FROM captures/ IS EVER WRITTEN INTO THE REPO by this
script — the fixture and the taps go to a scratch directory.

The Python column is a re-statement of ``pakon_ansel.AnselEngine.render_scene``'s
call sequence with taps inserted, calling the same library functions. That is
only trustworthy if it is the same computation, so with ``--stage-order
shasta-fugc`` (render_scene's own order) the harness asserts the driver and
``render_scene`` agree bit-for-bit at the ``ansel`` tap, and fails if they do
not.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "ansel" / "python-pipeline"))

GO_DIR = REPO / "tools" / "ansel" / "pipeline"

TAPS = ["poly", "inv", "balance", "shasta", "fugc", "ansel", "icc"]


# --------------------------------------------------------------------------
# fixture
# --------------------------------------------------------------------------

def synthetic_frame(h: int, w: int, seed: int = 20260810) -> np.ndarray:
    """A deterministic 14-bit frame that exercises the whole chain.

    Three things it has to do, none of which a random array does:

    * carry a CLEAR FILM BASE. FindDmin walks the histogram down from the top
      and returns 0 — its "no valid Dmin" sentinel — unless there is a bright
      population holding fewer than 0.1 % of the pixels above it. A frame with
      no leader refuses to render, which is correct behaviour and useless as a
      fixture.
    * NOT clip — and the ceiling that matters is the POLYNOMIAL's, not the
      sensor's. FindDmin runs on stage 2's linear 12-bit output, so a value
      that is comfortably under 16383 at the sensor can still land on 4095
      after fcn.1000d880 (whose diagonal is ~0.29 and whose green channel
      carries a +445 pedestal) and drive FindDmin to the sentinel. The levels
      below were picked by running the real polynomial: the leader lands at
      (2998, 3812, 3570) and the body tops out at (2644, 3375, 3254).
    * span the input domain. The stage-2 polynomial is quadratic and its
      cross terms only show up where the channels differ, so the body is a
      2-D ramp with per-channel gains plus a decorrelating noise term.
    """
    rng = np.random.default_rng(seed)
    yy = np.linspace(0.0, 1.0, h, dtype=np.float64)[:, None]
    xx = np.linspace(0.0, 1.0, w, dtype=np.float64)[None, :]

    out = np.empty((h, w, 3), dtype=np.float64)
    # Per-channel gain/offset roughly matching a colour negative's orange
    # mask: the blue record sits highest, the red lowest.
    for c, (lo, hi) in enumerate(((1800.0, 8200.0), (2600.0, 8800.0), (3400.0, 9200.0))):
        base = lo + (hi - lo) * (0.55 * yy + 0.45 * xx)
        base = base + 900.0 * np.sin(6.0 * np.pi * xx + 1.7 * c) * np.cos(4.0 * np.pi * yy)
        base = base + rng.normal(0.0, 140.0, size=(h, w))
        out[:, :, c] = base

    # Clear film base: the top ~3 % of rows, above the body but below the
    # polynomial's 4095 ceiling in every channel.
    lead = max(1, int(round(h * 0.03)))
    out[:lead, :, 0] = 10500.0 + rng.normal(0.0, 25.0, size=(lead, w))
    out[:lead, :, 1] = 11000.0 + rng.normal(0.0, 25.0, size=(lead, w))
    out[:lead, :, 2] = 11500.0 + rng.normal(0.0, 25.0, size=(lead, w))

    return np.clip(np.rint(out), 0, 16383).astype(np.uint16)


# --------------------------------------------------------------------------
# the Python column
# --------------------------------------------------------------------------

class PyRun:
    def __init__(self, taps: dict[str, np.ndarray], meta: dict):
        self.taps = taps
        self.meta = meta


def run_python(raw14: np.ndarray, cfg) -> PyRun:
    import pakon_color as pc
    import pakon_decode as dec
    import pakon_ansel as ansel
    import pakon_fugc as fugc_mod
    import pakon_sba_apply as sba_apply
    import pakon_scene_context as scene_ctx
    import pakon_color_adjust as color_adjust

    taps: dict[str, np.ndarray] = {}
    meta: dict = {}

    film_class = pc.film_class_for_path(cfg.film_path)
    dec.check_film_class(film_class, cfg.model)

    if cfg.coeff_source == "eeprom":
        coeffs, _ = pc.load_matrix_eeprom(film_class=film_class)
        coeffs = [pc.f32(v) for v in coeffs]
    else:
        coeffs = pc.load_unit_matrix("registry", film_class=film_class)
    meta["coeffs_diag"] = [coeffs[0], coeffs[11], coeffs[22]]

    # --- stage 2 ---
    poly = pc.poly_hwc(raw14, coeffs, film_class=film_class).astype(np.float64)
    if cfg.rpd16_roundtrip:
        # What cmd_strip actually does: render_rpd stores the 12-bit poly
        # output as u16 (rint(v * 65535/4095)) and ansel.rpd16_to_rpd12 scales
        # it back. It is a near-identity with sub-code error, and it is a real
        # part of the Python path, so it is on by default and reported.
        u16 = np.rint(poly * (65535.0 / 4095.0)).astype(np.uint16)
        poly = ansel.rpd16_to_rpd12(u16, pc.RPD_MAX_BY_MODEL["f135"])
    taps["poly"] = poly

    # --- Ansel tables, from the same .map selection Go runs ---
    scene = ansel.scene_from_filmstock(
        path=cfg.film_path,
        dx_part1=cfg.dx1 if cfg.dx1 >= 0 else None,
        dx_part2=cfg.dx2 if cfg.dx2 >= 0 else None,
        iso=cfg.iso,
    )
    engine = ansel.AnselEngine.load(cfg.ansel_root, scene=scene)
    engine.rpd_max = ansel.SHASTA_MAX
    engine.shasta_stand_in = True
    meta["sba_key"] = getattr(engine.selected, "sba_key", None)
    meta["fugc_lut"] = engine.fugc_name
    meta["setshifts"] = list(map(int, engine.setshifts_out))
    meta["fpo"] = list(engine.sba.fpo)
    meta["a_table_dmin"] = list(engine.fugc_a_table_dmin)
    meta["afilm_aim"] = list(engine.fugc_afilm_aim_dmin)

    # --- inversion, with the ROLL's film base ---
    # The balance shift runs in the LINEAR domain inside f135_rom12_to_rpd12
    # (docs/74 SS60), so `inv` already arrives balanced; the old separate
    # apply_balance_shifts pass is gone to avoid shifting the density twice.
    ped = (coeffs[9], coeffs[19], coeffs[29])
    inv = dec.f135_rom12_to_rpd12(
        poly, ped, engine.sba.fpo, engine.setshifts_out,
        quiet=True, film_base=tuple(float(v) for v in cfg.film_base),
    )
    taps["inv"] = inv

    # --- balance apply (now a no-op: already applied above) ---
    balanced = inv.astype(np.float64)
    taps["balance"] = balanced

    # --- FUGC aim words: ebp18 is FindDmin on the post-balance, pre-Shasta
    #     array, which is where pakon_ansel.py measures it too.
    bal16 = np.clip(balanced, 0, ansel.SHASTA_MAX).astype(np.int16)
    ebp18 = scene_ctx.frame_dmin_rgb_from_planes(
        bal16[:, :, 0].ravel(), bal16[:, :, 1].ravel(), bal16[:, :, 2].ravel())
    meta["ebp18"] = list(map(int, ebp18))
    meta["ebp18_policy_pass"] = bool(
        fugc_mod.fugc_ebp18_policy_pass(ebp18, engine.fugc_afilm_aim_dmin))

    seed = engine.fugc_lut.astype(np.int32, copy=False)
    if cfg.fugc_mode == 2:
        apply_lut, bias, aims = fugc_mod.build_mode2_apply_lut(
            seed,
            a_table_dmin=engine.fugc_a_table_dmin,
            arg_ebp14=engine.setshifts_out,
            arg_ebp18=ebp18,
            cap_params_aim=engine.fugc_afilm_aim_dmin,
        )
        meta["fugc_bias"] = int(bias)
        meta["fugc_offsets"] = None
    else:
        apply_lut, offs, aims = fugc_mod.build_setlutinfo_apply_lut(
            seed,
            a_table_dmin=engine.fugc_a_table_dmin,
            arg_ebp14=engine.setshifts_out,
            arg_ebp18=ebp18,
            cap_params_aim=engine.fugc_afilm_aim_dmin,
        )
        meta["fugc_bias"] = None
        meta["fugc_offsets"] = list(map(int, offs))
    meta["fugc_aims"] = {k: list(map(int, v)) for k, v in aims.items()}

    def do_shasta(x):
        return ansel.shasta_two_anchor_tone(x, engine.shasta)

    def do_fugc(x):
        return ansel.apply_1d_lut(x, apply_lut)

    if cfg.stage_order == "shasta-fugc":
        s = do_shasta(balanced)
        taps["shasta"] = s
        f = do_fugc(s)
        taps["fugc"] = f
        toned = f
    else:
        f = do_fugc(balanced)
        taps["fugc"] = f
        s = do_shasta(f)
        taps["shasta"] = s
        toned = s

    # ColorAdjust leaf: factory-zero params, so this is a no-op today. Run it
    # anyway rather than assume, because "it is skipped" is a property of the
    # params, not of the code.
    img16 = np.clip(toned, 0, ansel.SHASTA_MAX).astype(np.int16)
    img16 = color_adjust.apply_preference_color_adjust_i16(img16, engine.color_adjust)
    toned = np.clip(img16.astype(np.float64), 0, ansel.SHASTA_MAX)
    taps["ansel"] = toned

    # --- the driver is only worth anything if it IS render_scene ---
    #
    # render_scene only knows one order (its own), so the check runs the
    # driver at that order regardless of what the run is measuring. It is one
    # extra pass and it is the only thing standing between "the Python column"
    # and "a plausible-looking straw man".
    if cfg.check_driver:
        if cfg.stage_order == "shasta-fugc":
            drv = toned
        else:
            s2 = do_shasta(balanced)
            drv = do_fugc(s2)
            i16 = np.clip(drv, 0, ansel.SHASTA_MAX).astype(np.int16)
            drv = np.clip(color_adjust.apply_preference_color_adjust_i16(
                i16, engine.color_adjust).astype(np.float64), 0, ansel.SHASTA_MAX)
        ref = engine.render_scene(inv.astype(np.int16))
        diff = int(np.count_nonzero(np.asarray(ref, dtype=np.float64) - drv))
        meta["driver_vs_render_scene_differing_samples"] = diff
        if diff:
            raise SystemExit(
                f"parity driver disagrees with AnselEngine.render_scene in "
                f"{diff} samples. The driver is supposed to be the same "
                f"computation with taps; if it is not, every Python number "
                f"below is measuring the wrong thing. Fix the driver before "
                f"reading anything else.")

    taps["icc"] = engine.to_srgb(toned).astype(np.float64)
    meta["icc_input_depth"] = "u8 (PIL/lcms; PIL has no 16-bit RGB mode)"
    return PyRun(taps, meta)


# --------------------------------------------------------------------------
# the Go column
# --------------------------------------------------------------------------

def build_go(scratch: Path, quiet: bool = False) -> Path:
    """Build the Go pipeline into the scratch dir.

    Built fresh every run, into scratch, on purpose. docs/62 §5.2 found two
    same-sized different-content binaries in tools/ansel/pipeline/ with
    identical buildinfo, both older than their own sources: there is no way to
    tell what produced either. A harness that measured one of those would be
    measuring an unknown program.
    """
    out = scratch / "pakonpipeline"
    t0 = time.time()
    subprocess.run(
        ["go", "build", "-o", str(out), "."],
        cwd=GO_DIR, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if not quiet:
        print(f"  built {out.name} from {GO_DIR} in {time.time() - t0:.1f}s")
    return out


def run_go(binary: Path, raw_path: Path, h: int, w: int, cfg, scratch: Path) -> tuple[dict, dict]:
    tap_dir = scratch / "go-taps"
    dx = f"{cfg.dx1}-{cfg.dx2}" if cfg.dx2 >= 0 else str(cfg.dx1)
    argv = [
        str(binary),
        "-model", cfg.model,
        "-dx", dx,
        "-iso", str(cfg.iso),
        "-film-path", cfg.film_path,
        "-ansel-path", cfg.ansel_path,
        "-source-type", str(cfg.source_type),
        "-coeff-source", cfg.coeff_source,
        "-film-base", ",".join(str(int(v)) for v in cfg.film_base),
        "-stage-order", cfg.stage_order,
        "-icc-input", cfg.icc_input,
        "-fugc-mode", str(cfg.fugc_mode),
        "-ansel-root", str(cfg.ansel_root),
        "-raw-in", f"{h},{w}",
        "-tap-dir", str(tap_dir),
        str(raw_path),
    ]
    proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr.decode(errors="replace"))
        raise SystemExit(f"go pipeline failed ({proc.returncode})")
    if proc.stdout.strip():
        # The ABI in docs/62 §3.4 requires stdout to stay clean. This is where
        # a regression on that shows up.
        raise SystemExit(
            "the Go pipeline wrote to stdout:\n"
            + proc.stdout.decode(errors="replace")
            + "\nEverything it logs must go to stderr — an app driving it over "
              "a pipe cannot tell a log line from a payload.")

    manifest = json.loads((tap_dir / "manifest.json").read_text())
    taps: dict[str, np.ndarray] = {}
    for name in manifest["taps"]:
        f64 = tap_dir / f"{name}.f64"
        u8 = tap_dir / f"{name}.u8"
        if f64.is_file():
            taps[name] = np.fromfile(f64, dtype="<f8").reshape(h, w, 3)
        else:
            taps[name] = np.fromfile(u8, dtype=np.uint8).reshape(h, w, 3).astype(np.float64)
    return taps, manifest


# --------------------------------------------------------------------------
# comparison
# --------------------------------------------------------------------------

def compare(name: str, a: np.ndarray, b: np.ndarray) -> dict:
    d = np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)
    ad = np.abs(d)
    n = d.size
    return {
        "tap": name,
        "mean_py": [float(v) for v in np.asarray(a, np.float64).mean(axis=(0, 1))],
        "mean_go": [float(v) for v in np.asarray(b, np.float64).mean(axis=(0, 1))],
        "mean_signed_delta": [float(v) for v in d.mean(axis=(0, 1))],
        "mean_abs_delta": [float(v) for v in ad.mean(axis=(0, 1))],
        "max_abs_delta": [float(v) for v in ad.max(axis=(0, 1))],
        "p999_abs_delta": [float(np.percentile(ad[:, :, c], 99.9)) for c in range(3)],
        "differing_samples": int(np.count_nonzero(ad > 0)),
        "differing_pct": 100.0 * float(np.count_nonzero(ad > 0)) / n,
        "gt1_pct": 100.0 * float(np.count_nonzero(ad > 1.0)) / n,
    }


def print_report(rows: list[dict], py_meta: dict, go_meta: dict, cfg) -> bool:
    print()
    print(f"{'tap':<9} {'differ%':>8} {'>1code%':>8} "
          f"{'mean|d| R/G/B':>24} {'p99.9|d|':>20} {'max|d| R/G/B':>20}")
    print("-" * 88)
    worst = 0.0
    for r in rows:
        m = "/".join(f"{v:.4f}" for v in r["mean_abs_delta"])
        q = "/".join(f"{v:.3f}" for v in r["p999_abs_delta"])
        x = "/".join(f"{v:.3f}" for v in r["max_abs_delta"])
        print(f"{r['tap']:<9} {r['differing_pct']:>7.2f}% {r['gt1_pct']:>7.2f}% "
              f"{m:>24} {q:>20} {x:>20}")
        worst = max(worst, max(r["max_abs_delta"]))
    print("-" * 88)

    print("\nper-tap channel means (python -> go)")
    for r in rows:
        py = "/".join(f"{v:.1f}" for v in r["mean_py"])
        go = "/".join(f"{v:.1f}" for v in r["mean_go"])
        print(f"  {r['tap']:<9} {py:>24}   ->   {go:>24}")

    print("\nselection and aim words")
    print(f"  python: fugc lut {py_meta.get('fugc_lut')}  "
          f"setshifts {py_meta.get('setshifts')}  ebp18 {py_meta.get('ebp18')} "
          f"(policy pass {py_meta.get('ebp18_policy_pass')})")
    gsel = go_meta.get("selection", {})
    greq = go_meta.get("request", {})
    print(f"  go    : fugc lut {gsel.get('fugcLut')} via {gsel.get('fugcMap')} "
          f"(mode {gsel.get('fugcMode')})  setshifts {go_meta.get('setshifts')}  "
          f"ebp18 {go_meta.get('ebp18')} (policy pass {go_meta.get('ebp18PolicyPass')})")
    print(f"  python fugc bias {py_meta.get('fugc_bias')} offsets {py_meta.get('fugc_offsets')}")
    print(f"  go     fugc bias {go_meta.get('fugcBias')} offsets {go_meta.get('fugcOffsets')}")
    print(f"  film base (roll, both) {cfg.film_base}   "
          f"go source: {go_meta.get('filmBaseSource')}")
    print(f"  stage order {greq.get('stageOrder')}   icc input "
          f"go={greq.get('iccInput')} python={py_meta.get('icc_input_depth')}")
    if "driver_vs_render_scene_differing_samples" in py_meta:
        print(f"  python driver vs AnselEngine.render_scene: "
              f"{py_meta['driver_vs_render_scene_differing_samples']} differing samples")
    return worst == 0.0


# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--height", type=int, default=192)
    ap.add_argument("--width", type=int, default=256)
    ap.add_argument("--raw", type=Path, default=None,
                    help="a real (h,w,3) little-endian u16 frame instead of the "
                         "synthetic fixture; needs --height/--width")
    ap.add_argument("--dx", default="96-1")
    ap.add_argument("--iso", type=int, default=400)
    ap.add_argument("--film-path", default="ColNeg")
    ap.add_argument("--ansel-path", default="CN-Premium")
    ap.add_argument("--source-type", type=int, default=1)
    ap.add_argument("--coeff-source", default="eeprom", choices=("eeprom", "registry"))
    ap.add_argument("--stage-order", default="fugc-shasta",
                    choices=("shasta-fugc", "fugc-shasta"),
                    help="fugc-shasta is the VENDOR's order, established from "
                         "PakonIMAu.dll (docs/62 §12.4) and what Go now defaults "
                         "to. shasta-fugc is what pakon_ansel.render_scene does")
    ap.add_argument("--icc-input", default="u8", choices=("u8", "u12"),
                    help="the Go side's ICC input depth. u8 puts it on Python's "
                         "footing; u12 is what the 4096-entry input table was built for")
    ap.add_argument("--fugc-mode", type=int, default=1)
    ap.add_argument("--model", default="f135")
    ap.add_argument("--ansel-root", type=Path, default=None)
    ap.add_argument("--no-rpd16-roundtrip", action="store_true",
                    help="skip the 12->16->12 bit round trip cmd_strip does. Off "
                         "by default because it is part of the Python path")
    ap.add_argument("--no-driver-check", action="store_true")
    ap.add_argument("--scratch", type=Path, default=None,
                    help="where to put the fixture, the binary and the taps. "
                         "Defaults to a temp dir that is removed on exit. NOTHING "
                         "is written inside the repo")
    ap.add_argument("--json", type=Path, default=None,
                    help="also write the full report here")
    ap.add_argument("--sensitivity", action="store_true",
                    help="also measure what the two unsettled choices cost: the\n                         stage order (python, both orders) and the ICC input\n                         depth (go, both depths)")
    ap.add_argument("--keep", action="store_true", help="keep the scratch dir")
    args = ap.parse_args()

    p1, _, p2 = args.dx.partition("-")
    cfg = argparse.Namespace(
        dx1=int(p1), dx2=int(p2) if p2 else -1,
        iso=args.iso, film_path=args.film_path, ansel_path=args.ansel_path,
        source_type=args.source_type, coeff_source=args.coeff_source,
        stage_order=args.stage_order, icc_input=args.icc_input,
        fugc_mode=args.fugc_mode, model=args.model,
        ansel_root=args.ansel_root or (REPO / "vendor" / "ansel" /
                                       "anselinstalldir" / "dataPathItems"),
        rpd16_roundtrip=not args.no_rpd16_roundtrip,
        check_driver=not args.no_driver_check,
        film_base=(0, 0, 0),
    )

    scratch = Path(args.scratch) if args.scratch else Path(tempfile.mkdtemp(prefix="pakon-parity-"))
    scratch.mkdir(parents=True, exist_ok=True)
    try:
        if args.raw:
            raw = np.fromfile(args.raw, dtype="<u2").reshape(args.height, args.width, 3)
            print(f"fixture: {args.raw} ({args.height}x{args.width})")
        else:
            raw = synthetic_frame(args.height, args.width)
            print(f"fixture: synthetic {args.height}x{args.width} "
                  f"(deterministic, generated — no capture data)")
        h, w = raw.shape[:2]
        raw_path = scratch / "frame.u16"
        raw.astype("<u2").tofile(raw_path)

        # The ROLL film base. Both engines are given the SAME number, because
        # that is the contract: it is a property of the stock measured over
        # the whole strip, and neither engine may measure its own. Here the
        # fixture is the whole "roll", so it is measured from it once.
        import pakon_color as pc
        import pakon_decode as dec
        coeffs = pc.load_unit_matrix("eeprom" if cfg.coeff_source == "eeprom"
                                     else "registry", film_class=1)
        lin = pc.poly_hwc(raw, coeffs, film_class=1)
        # Over the FILM, not over every pixel — dec.film_base_window. The
        # fixture is on the capture's own grid, so the CCD axis is x and the
        # columns below the vendor's window start (docs/53 §3.4) come off.
        base, win = dec.film_base_codes(lin)
        cfg.film_base = tuple(int(v) for v in base)
        print(f"roll film base (FindDmin over the fixture's film area — "
              f"columns {win['col0']}.., {win['lines_kept']}/"
              f"{win['lines_total']} lines): {cfg.film_base}")
        if min(cfg.film_base) <= 0:
            raise SystemExit(
                "the fixture has no measurable film base (FindDmin sentinel) "
                f"even over its film area — clipped "
                f"{win['clip_pct'][0]:.3f}/{win['clip_pct'][1]:.3f}/"
                f"{win['clip_pct'][2]:.3f}% there, against FindDmin's 0.1%. "
                "Both engines refuse this, correctly — the fixture is wrong, "
                "not the engines.")

        print("python:")
        t0 = time.time()
        py = run_python(raw, cfg)
        py_secs = time.time() - t0
        print(f"  {py_secs:.2f}s")

        print("go:")
        binary = build_go(scratch)
        t0 = time.time()
        go_taps, go_meta = run_go(binary, raw_path, h, w, cfg, scratch)
        go_secs = time.time() - t0
        print(f"  {go_secs:.2f}s")

        rows = []
        for name in TAPS:
            if name in py.taps and name in go_taps:
                rows.append(compare(name, py.taps[name], go_taps[name]))
            else:
                print(f"  (tap {name} missing: python={name in py.taps} "
                      f"go={name in go_taps})")

        clean = print_report(rows, py.meta, go_meta, cfg)

        sens: dict = {}
        if args.sensitivity:
            # How much do the two UNSETTLED choices actually cost? Both are
            # measured within one engine, so nothing else varies.
            import copy
            print("\nsensitivity — the size of the open questions")

            other_order = ("fugc-shasta" if cfg.stage_order == "shasta-fugc"
                           else "shasta-fugc")
            cfg2 = copy.copy(cfg)
            cfg2.stage_order = other_order
            cfg2.check_driver = False
            py2 = run_python(raw, cfg2)
            for t in ("ansel", "icc"):
                r = compare(t, py.taps[t], py2.taps[t])
                sens[f"stage_order/{t}"] = r
                print(f"  stage order {cfg.stage_order} vs {other_order}, python, "
                      f"{t}: {r['differing_pct']:.2f}% differ, mean|d| "
                      + "/".join(f"{v:.2f}" for v in r["mean_abs_delta"])
                      + ", max " + "/".join(f"{v:.0f}" for v in r["max_abs_delta"]))

            other_depth = "u12" if cfg.icc_input == "u8" else "u8"
            cfg3 = copy.copy(cfg)
            cfg3.icc_input = other_depth
            go3, _ = run_go(binary, raw_path, h, w, cfg3, scratch)
            r = compare("icc", go_taps["icc"], go3["icc"])
            sens["icc_depth/icc"] = r
            print(f"  icc input {cfg.icc_input} vs {other_depth}, go, icc: "
                  f"{r['differing_pct']:.2f}% differ, mean|d| "
                  + "/".join(f"{v:.2f}" for v in r["mean_abs_delta"])
                  + ", max " + "/".join(f"{v:.0f}" for v in r["max_abs_delta"]))
        print(f"\ntiming: python {py_secs:.2f}s   go {go_secs:.2f}s "
              f"(go includes table load; build excluded)")

        report = {
            "config": {k: (str(v) if isinstance(v, Path) else v)
                       for k, v in vars(cfg).items()},
            "shape": [h, w],
            "rows": rows,
            "python_meta": py.meta,
            "go_meta": go_meta,
            "seconds": {"python": py_secs, "go": go_secs},
            "sensitivity": sens,
        }
        if args.json:
            args.json.write_text(json.dumps(report, indent=1, default=str))
            print(f"wrote {args.json}")
        return 0 if clean else 1
    finally:
        if args.keep or args.scratch:
            print(f"scratch kept at {scratch}")
        else:
            shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
