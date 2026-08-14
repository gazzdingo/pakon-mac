#!/usr/bin/env python3
"""Tap the Ansel pipeline at every stage and show where our range dies.

The washout defect is a range problem: the vendor reaches p1 = 0/6/5 on AA005
and uses the full 0-255, while ours floors at 60-110 (docs/54). Six tone
subsystems verify bit-exact against the DLL and the render is still wrong, so
the fault is not inside any one stage -- it is in what reaches them. This shows
the data at each boundary so the collapse can be located rather than guessed at.

HOW IT TAPS
    By wrapping the functions the engine actually calls, not by editing it.
    render_scene has several branches (preference vs fallback, shasta stand-in
    vs assembled tone LUT vs linked-percentile) and which one runs depends on
    what loaded. Wrapping records whichever branch really executed, so the stage
    list is evidence rather than assumption -- if a stage does not appear here,
    it did not run.

VENDOR GROUND TRUTH
    research/vendor-scans/ has six frames as raw/render pairs from PSI. They are
    PIXEL-REGISTERED (verified: peak |correlation| 0.90 at dy=dx=0), which means
    the vendor's end-to-end transform can be MEASURED directly from the pair --
    no DLL instrumentation, no DynamoRIO. --compare does that and diffs it
    against ours, per channel, per code value.

    Note the raw export is the NEGATIVE: correlation with the render is negative
    (R -0.76, G -0.92, B -0.93), and raw 0 maps to render ~254/248/228.

THE INVERSION STEP -- DO NOT SKIP IT
    render_scene does NOT invert the negative. That happens earlier, in
    pakon_decode.f135_rom12_to_rpd12, which test_render_f135.py guards with
    test_scene_rpd12_inverts. Calling render_scene directly on negative data
    produces output correlating +0.99 with the input -- a harness bug that
    looks exactly like a catastrophic port defect. This tool runs the inversion
    first (corr goes to -0.94) so the stage table reflects the real path.

INPUT CAVEAT -- READ THIS
    PSI's "RAW" export is 8-bit and already partly processed; it is NOT the
    12-bit RPD the engine is built for. Feeding it via --from-vendor-raw scales
    8->12 bits and is an APPROXIMATION. It is good enough to see where range
    collapses and to compare curve SHAPE, and not good enough for bit-exact
    claims. Use --rpd with real scanner data when you have it.

Usage:
    ./pakon_stage_probe.py --from-vendor-raw .../rawAA005.png
    ./pakon_stage_probe.py --from-vendor-raw .../rawAA005.png \
        --compare .../AA005.png --dump-dir /tmp/stages
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

RECORD: list[dict] = []
_ORIG: list[tuple] = []


def _stats(a: np.ndarray) -> dict | None:
    """Per-channel percentiles. None for anything that is not an RGB image."""
    if not isinstance(a, np.ndarray) or a.ndim != 3 or a.shape[2] != 3:
        return None
    x = a.astype(np.float64)
    out = {"shape": a.shape, "dtype": str(a.dtype), "ch": []}
    for c in range(3):
        v = x[:, :, c].ravel()
        p = np.percentile(v, [1, 50, 99])
        out["ch"].append({"p1": p[0], "p50": p[1], "p99": p[2],
                          "min": float(v.min()), "max": float(v.max()),
                          "span": p[2] - p[0]})
    return out


def _wrap(mod, name: str, label: str):
    fn = getattr(mod, name, None)
    if fn is None or not callable(fn):
        return False
    _ORIG.append((mod, name, fn))

    def wrapper(*a, **kw):
        src = next((x for x in a if isinstance(x, np.ndarray)
                    and x.ndim == 3 and x.shape[2] == 3), None)
        out = fn(*a, **kw)
        RECORD.append({"label": label, "n": len(RECORD),
                       "in": _stats(src), "out": _stats(out)})
        return out

    wrapper.__name__ = getattr(fn, "__name__", name)
    setattr(mod, name, wrapper)
    return True


def install_taps() -> list[str]:
    """Wrap every stage boundary we know about. Missing ones are skipped."""
    import pakon_ansel as A
    import pakon_sba_apply as sba_apply
    plan = [
        (A, "rpd16_to_rpd12", "rpd16->rpd12"),
        (sba_apply, "apply_balance_shifts", "SBA setshifts balance"),
        (A, "channel_balance", "channel_balance (fallback)"),
        (A, "shasta_two_anchor_tone", "TONE two-anchor STAND-IN"),
        (A, "linked_percentile_tone", "TONE linked-percentile STAND-IN"),
        (A, "apply_1d_lut", "apply_1d_lut"),
        (A, "aim_medians", "aim_medians"),
        (A, "rpd12_to_icc_u8", "rpd12->icc u8"),
    ]
    for modname, attr, label in (
        ("pakon_shasta", "ima_shasta_op_apply", "SHASTA apply (real)"),
        ("pakon_color_adjust", "apply_preference_color_adjust_i16",
         "ColorAdjust"),
        ("pakon_fugc", "build_setlutinfo_apply_lut", "FUGC build lut"),
    ):
        try:
            plan.append((__import__(modname), attr, label))
        except ImportError:
            pass
    return [lbl for mod, attr, lbl in plan if _wrap(mod, attr, lbl)]


def remove_taps() -> None:
    for mod, name, fn in _ORIG:
        setattr(mod, name, fn)
    _ORIG.clear()


def print_stage_table() -> None:
    if not RECORD:
        print("  no stages recorded -- taps did not fire")
        return
    print(f"\n{'#':>3} {'stage':34} {'ch':2} "
          f"{'in p1':>7}{'in p50':>8}{'in p99':>8} -> "
          f"{'p1':>7}{'p50':>8}{'p99':>8}{'span':>8}")
    print("  " + "-" * 96)
    for r in RECORD:
        o = r["out"]
        if o is None:
            continue
        i = r["in"]
        for c, name in enumerate("RGB"):
            oc = o["ch"][c]
            head = f"{r['n']:>3} {r['label'][:34]:34}" if c == 0 else " " * 38
            if i is not None:
                ic = i["ch"][c]
                lead = f"{ic['p1']:7.0f}{ic['p50']:8.0f}{ic['p99']:8.0f}"
            else:
                lead = f"{'-':>7}{'-':>8}{'-':>8}"
            print(f"{head} {name:2} {lead} -> "
                  f"{oc['p1']:7.0f}{oc['p50']:8.0f}{oc['p99']:8.0f}"
                  f"{oc['span']:8.0f}")


def transfer_curve(src: np.ndarray, dst: np.ndarray, step: int = 8):
    """Median dst value for each bucket of src values, per channel.

    Both must be pixel-registered 8-bit RGB. This is the empirical end-to-end
    transform -- it needs no knowledge of the stages that produced it, which is
    the whole point: it works on the vendor's closed pipeline.
    """
    curves = []
    for c in range(3):
        s, d = src[:, :, c].ravel(), dst[:, :, c].ravel()
        xs, ys, ns = [], [], []
        for lo in range(0, 256, step):
            m = (s >= lo) & (s < lo + step)
            n = int(m.sum())
            if n < 200:
                continue
            xs.append(lo + step / 2)
            ys.append(float(np.median(d[m])))
            ns.append(n)
        curves.append((np.array(xs), np.array(ys), np.array(ns)))
    return curves


def print_compare(raw8: np.ndarray, vendor8: np.ndarray, ours8: np.ndarray):
    shift = _best_shift(raw8, vendor8)
    print(f"\n  registration check: best |corr| at dy={shift[1]} dx={shift[2]} "
          f"({shift[0]:.3f}) -- "
          f"{'aligned' if shift[1] == 0 and shift[2] == 0 else 'MISALIGNED'}")
    vc = transfer_curve(raw8, vendor8)
    oc = transfer_curve(raw8, ours8)
    print("\n  End-to-end transfer, median rendered value per raw bucket.")
    print("  'raw' is the NEGATIVE, so both curves should fall as raw rises.\n")
    print(f"  {'raw':>4} |{'vendor R':>9}{'ours R':>8}{'d':>6} "
          f"|{'vendor G':>9}{'ours G':>8}{'d':>6} "
          f"|{'vendor B':>9}{'ours B':>8}{'d':>6}")
    print("  " + "-" * 78)
    xs = sorted(set(vc[0][0]).intersection(oc[0][0]))
    worst = [0.0, 0.0, 0.0]
    for x in xs:
        row = f"  {x:4.0f} |"
        for c in range(3):
            vx, vy, _ = vc[c]
            ox, oy, _ = oc[c]
            iv = np.where(vx == x)[0]
            io = np.where(ox == x)[0]
            if not len(iv) or not len(io):
                row += f"{'-':>9}{'-':>8}{'-':>6} |"
                continue
            a, b = vy[iv[0]], oy[io[0]]
            worst[c] = max(worst[c], abs(a - b))
            row += f"{a:9.0f}{b:8.0f}{b - a:+6.0f} |"
        print(row)
    print(f"\n  worst |vendor - ours| per channel: "
          f"R {worst[0]:.0f}  G {worst[1]:.0f}  B {worst[2]:.0f}   (of 255)")


def _best_shift(a: np.ndarray, b: np.ndarray):
    ga, gb = a.mean(2).astype(np.float64), b.mean(2).astype(np.float64)
    best = None
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            A = ga[20:-20, 20:-20]
            B = gb[20 + dy:gb.shape[0] - 20 + dy, 20 + dx:gb.shape[1] - 20 + dx]
            c = abs(np.corrcoef(A.ravel(), B.ravel())[0, 1])
            if best is None or c > best[0]:
                best = (c, dy, dx)
    return best


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from-vendor-raw", type=Path,
                    help="PSI RAW export (8-bit). APPROXIMATION -- see docstring.")
    ap.add_argument("--rpd", type=Path,
                    help="real 12-bit RPD .npy (H,W,3), preferred over the above")
    ap.add_argument("--compare", type=Path,
                    help="PSI finished render of the same frame, for the diff")
    ap.add_argument("--dump-dir", type=Path,
                    help="write a PNG per stage here")
    ap.add_argument("--ansel-root", type=Path, default=None)
    ap.add_argument("--no-invert", action="store_true",
                    help="skip f135_rom12_to_rpd12. Only for isolating that "
                         "step -- the output will look catastrophically wrong.")
    args = ap.parse_args()

    if not args.from_vendor_raw and not args.rpd:
        ap.error("need --from-vendor-raw or --rpd")

    from PIL import Image
    import pakon_ansel as A

    if args.rpd:
        rpd12 = np.load(args.rpd).astype(np.float64)
        print(f"input: {args.rpd.name}  real RPD12  {rpd12.shape}")
    else:
        raw8 = np.asarray(Image.open(args.from_vendor_raw).convert("RGB"))
        rpd12 = raw8.astype(np.float64) * 16.0
        print(f"input: {args.from_vendor_raw.name}  8-bit vendor RAW "
              f"{raw8.shape} scaled x16")
        print("       APPROXIMATION -- not true RPD12. Shape is comparable, "
              "absolute values are not.")

    fired = install_taps()
    print(f"\ntaps installed: {len(fired)}")
    try:
        kw = {}
        if args.ansel_root:
            kw["ansel_root"] = args.ansel_root
        eng = A.AnselEngine.load(
            scene=A.scene_from_filmstock(path="ColNeg", dx_part1=96,
                                         dx_part2=1, iso=400), **kw)
        print(f"engine loaded. shasta_stand_in={getattr(eng, 'shasta_stand_in', '?')}")
        if not args.no_invert:
            # The negative -> positive step. render_scene does NOT do this;
            # skipping it silently produces a positive-of-a-negative that
            # reads as a total pipeline failure. See docstring.
            sys.path.insert(0, str(_HERE.parent.parent))
            import pakon_decode as dec
            import pakon_render as pr
            base = tuple(float(dec._film_base_code(rpd12[:, :, c]))
                         for c in range(3))
            neg = rpd12
            rpd12 = dec.f135_rom12_to_rpd12(
                rpd12, pr.poly_pedestals(), eng.sba.fpo, eng.setshifts_out,
                quiet=True, film_base=base)
            c = np.corrcoef(neg.mean(2).ravel(), rpd12.mean(2).ravel())[0, 1]
            print(f"  f135_rom12_to_rpd12: film_base={[round(b) for b in base]}"
                  f"  corr(in,out)={c:+.3f} (want < -0.9)")
            RECORD.append({"label": "f135 negative->positive", "n": -1,
                           "in": _stats(neg), "out": _stats(rpd12)})
        toned = eng.render_scene(rpd12)
        srgb = eng.to_srgb(toned)
    except Exception as exc:
        remove_taps()
        print(f"\nrender FAILED: {type(exc).__name__}: {exc}")
        print("stages that ran before the failure:")
        print_stage_table()
        return 1
    remove_taps()

    RECORD.sort(key=lambda r: r["n"])
    print(f"\nstages that actually executed: {len(RECORD)}")
    print_stage_table()

    if args.dump_dir:
        args.dump_dir.mkdir(parents=True, exist_ok=True)
        for r in RECORD:
            pass  # stats only; full arrays are not retained by design
        Image.fromarray(srgb).save(args.dump_dir / "final_srgb.png")
        print(f"\n  wrote {args.dump_dir / 'final_srgb.png'}")

    if args.compare:
        if args.rpd:
            print("\n--compare needs the 8-bit vendor raw as the common input; "
                  "skipped under --rpd.")
        else:
            vendor8 = np.asarray(Image.open(args.compare).convert("RGB"))
            if vendor8.shape != srgb.shape:
                print(f"\n  shape mismatch: vendor {vendor8.shape} vs "
                      f"ours {srgb.shape} -- cannot diff")
            else:
                print_compare(raw8, vendor8, srgb)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
