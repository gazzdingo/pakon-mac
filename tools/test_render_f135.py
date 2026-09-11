#!/usr/bin/env python3
"""The app's F-135 render path must invert the negative. Regression test.

Why this file exists
--------------------
``tools/pakon_render.py`` is the app's image path: ``export_frame`` calls
``render_frame`` and writes what it returns. For a while ``render_frame`` ran
stage 2 and went straight to Ansel, never calling the F-135 negative -> positive
step — so every colour-negative frame the app exported was a NEGATIVE. Nothing
downstream noticed, and nothing could: ``apply_correction`` is additive, and
``render_scene``'s ``setshifts_out`` branch is a balance offset plus tone LUTs,
none of which change polarity. The exported file was simply wrong, silently.

So the test is a polarity test, not a golden-image test. It uses no capture —
the repo is public and ``captures/`` is the owner's photographs — only a
synthetic negative and the vendor data that ships in ``vendor/ansel``.

Run: ``python3 tools/test_render_f135.py``
"""

import os
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "ansel", "python-pipeline"))

import pakon_ansel as ansel          # noqa: E402
import pakon_color as pc             # noqa: E402
import pakon_decode as dec           # noqa: E402
import pakon_render as pr            # noqa: E402

WIDTH = dec.PIXELS_PER_LINE
LINES = 240


def synthetic_negative(lines: int = LINES) -> np.ndarray:
    """A 14-bit strip that behaves like a colour negative.

    Transmission rises left to right, so the SCENE gets darker left to right —
    that is what makes the polarity assertion below meaningful. The right-hand
    band is clear film, which is what FindDmin has to land on.
    """
    ramp = np.linspace(300.0, 11000.0, WIDTH, dtype=np.float64)
    img = np.repeat(ramp[None, :], lines, axis=0)
    # Orange mask: the base transmits red most, blue least.
    rgb = np.stack([img * 1.00, img * 0.72, img * 0.55], axis=-1)
    # A clear-film band — the film base FindDmin must find.
    rgb[:, -WIDTH // 20:, :] = np.array([11000.0, 7920.0, 6050.0])
    return np.clip(rgb, 0, dec.RAW14_MAX).astype(np.uint16)


def build_engine():
    eng = ansel.AnselEngine.load(
        dec.DEFAULT_ANSEL_ROOT,
        scene=ansel.scene_from_filmstock(
            path="ColNeg", dx_part1=96, dx_part2=1, iso=400),
    )
    eng.rpd_max = ansel.SHASTA_MAX
    eng.shasta_stand_in = True
    return eng


def corr(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.corrcoef(np.asarray(a, dtype=np.float64).ravel(),
                             np.asarray(b, dtype=np.float64).ravel())[0, 1])


# --------------------------------------------------------------------------


def test_stage2_alone_is_still_a_negative(seg, eng) -> list[str]:
    """Guard the premise: nothing in stage 2 inverts, so the step is required."""
    fails = []
    r16 = pr._rpd16(seg, dec.DEFAULT_DATA_DIR, np.zeros(3), model="f135")
    lin = ansel.rpd16_to_rpd12(r16, pc.RPD_MAX_BY_MODEL["f135"])
    c = corr(seg[:, :, 1], lin[:, :, 1])
    print(f"  stage 2 alone: corr(raw14, rpd12) = {c:+.3f}  (want > +0.9)")
    if not c > 0.9:
        fails.append(f"stage 2 no longer preserves polarity (corr={c:+.3f}); "
                     f"the premise of the F-135 invert has changed")
    if int(lin.max()) >= 4095:
        fails.append("synthetic negative clips the polynomial ceiling; "
                     "the fixture, not the code, needs adjusting")
    return fails


def test_scene_rpd12_inverts(seg, eng) -> list[str]:
    """The whole point: the app's stage-2 output must come out positive."""
    fails = []
    base = tuple(
        float(dec._film_base_code(
            ansel.rpd16_to_rpd12(
                pr._rpd16(seg, dec.DEFAULT_DATA_DIR, np.zeros(3),
                          model="f135"),
                pc.RPD_MAX_BY_MODEL["f135"])[:, :, c]))
        for c in range(3)
    )
    rpd12 = pr.scene_rpd12(seg, dec.DEFAULT_DATA_DIR, np.zeros(3),
                           "f135", eng, base)
    c = corr(seg[:, :, 1], rpd12[:, :, 1])
    print(f"  scene_rpd12:   corr(raw14, rpd12) = {c:+.3f}  (want < -0.9)")
    if not c < -0.9:
        fails.append(
            f"scene_rpd12 did not invert the negative (corr={c:+.3f}). "
            f"THIS IS THE BUG: the F-135 negative->positive step is missing "
            f"from the app's image path, so every exported colour-negative "
            f"frame is a negative.")

    # And it must be the vendor-cited step, not some other polarity flip.
    #
    # WHICH step that is depends on PAKON_VENDOR_INVERT. This assertion used to
    # hard-code the legacy reference, so running the suite with the flag set
    # failed with "max delta 560.495" — not a regression, but a test that did
    # not know the flag existed. The flag has been opt-in since the vendor
    # inversion landed (docs/74 §170-§175); nothing had ever run this file with
    # it on. Assert each architecture against ITS OWN reference rather than
    # skipping, so both paths stay covered.
    if os.environ.get("PAKON_VENDOR_INVERT") == "1":
        # The vendor's own position: invert the RAW code with the captured
        # table BEFORE the polynomial — no film base, no Dmin, no pedestal,
        # no fpo — then poly, then rpd16 -> rpd12. No second inversion.
        lut = pr._vendor_invert_lut()
        inv = lut[np.clip(np.asarray(seg, dtype=np.int32), 0, lut.size - 1)]
        ref = ansel.rpd16_to_rpd12(
            pr._rpd16(inv.astype(np.uint16), dec.DEFAULT_DATA_DIR,
                      np.zeros(3), model="f135"),
            pc.RPD_MAX_BY_MODEL["f135"])
        label = "vendor inversion (PAKON_VENDOR_INVERT=1)"
    else:
        ref = dec.f135_rom12_to_rpd12(
            ansel.rpd16_to_rpd12(
                pr._rpd16(seg, dec.DEFAULT_DATA_DIR, np.zeros(3),
                          model="f135"),
                pc.RPD_MAX_BY_MODEL["f135"]),
            pr.poly_pedestals(), eng.sba.fpo, eng.setshifts_out,
            quiet=True, film_base=base)
        label = "pakon_decode.f135_rom12_to_rpd12"
    worst = float(np.abs(rpd12 - ref).max())
    print(f"  vs {label}: max delta {worst:g}")
    if worst != 0.0:
        fails.append(f"scene_rpd12 is not {label} (max delta {worst:g})")
    return fails


def test_render_frame_inverts(seg, eng) -> list[str]:
    """End to end through the real ``render_frame``, the way export does."""
    fails = []
    with tempfile.TemporaryDirectory(prefix="pakon-f135-") as tmp:
        ws = os.path.join(tmp, "roll")
        os.makedirs(ws, exist_ok=True)
        roll = pr.Roll(id="t", name="t", capture=os.path.join(tmp, "none.bin"),
                       workspace=ws, lines=seg.shape[0], dx="96-1",
                       model="f135", transport_scale=1.0, film_path="ColNeg")
        np.save(roll.cache_path, seg)
        # slice14 undoes the unit dark/gain, so pre-multiply them back in to
        # get the fixture out the other side unchanged.
        dark, gain, _ = dec.load_unit_calibration()
        np.save(roll.cache_path,
                np.clip(seg.astype(np.float64) / gain + dark,
                        0, dec.RAW14_MAX).astype(np.uint16))
        roll.frames = [pr.Frame(index=0, a=0, b=seg.shape[0])]
        roll.auto_offsets = [0.0, 0.0, 0.0]
        roll.film_base = [
            float(dec._film_base_code(
                ansel.rpd16_to_rpd12(
                    pr._rpd16(roll.slice14(0, seg.shape[0], 1),
                              roll.data_dir, np.zeros(3), model="f135"),
                    pc.RPD_MAX_BY_MODEL["f135"])[:, :, c]))
            for c in range(3)
        ]
        img = pr.render_frame(roll, 0, None, scale="full")

    # render_frame rot90s for display AND applies _display_orient (the vendor
    # upright 180°, measured against the real vendor output TIFFs); compare
    # against the same composed transform of the input rather than assuming an
    # orientation. This test is about polarity (does the render invert the
    # negative), not orientation -- keep the reference in render_frame's own
    # display frame so a correct orientation change cannot masquerade as an
    # inversion regression.
    raw_disp = pr._display_orient(dec.to_frame_image(seg, 1.0))
    if raw_disp.shape[:2] != img.shape[:2]:
        fails.append(f"shape mismatch: raw {raw_disp.shape} vs {img.shape}")
        return fails
    c = corr(raw_disp[:, :, 1], img[:, :, 1])
    mean = img.reshape(-1, 3).mean(axis=0)
    print(f"  render_frame:  corr(raw14, sRGB) = {c:+.3f}  (want < 0)  "
          f"mean RGB = {mean.round(1)}")
    if not c < 0.0:
        fails.append(
            f"render_frame returned a NEGATIVE (corr={c:+.3f}). export_frame "
            f"writes exactly this, so every exported frame would be inverted.")
    return fails


def test_rpd_max_round_trip() -> list[str]:
    """4092 is the F-235 ceiling. Using it on F-135 loses ~2 codes of 4096."""
    fails = []
    codes = np.arange(4096, dtype=np.int64)
    fwd = np.rint(codes * (65535.0 / pc.RPD_MAX_BY_MODEL["f135"]))
    fwd = np.clip(fwd, 0, 65535).astype(np.uint16)

    right = ansel.rpd16_to_rpd12(fwd, pc.RPD_MAX_BY_MODEL["f135"])
    err_right = np.abs(right - codes)
    wrong = ansel.rpd16_to_rpd12(fwd)          # the F-235 default, 4092
    err_wrong = np.abs(wrong - codes)

    print(f"  round trip @4095: mean err {err_right.mean():.4f}  "
          f"max {err_right.max():.4f}")
    print(f"  round trip @4092: mean err {err_wrong.mean():.4f}  "
          f"max {err_wrong.max():.4f}")
    if err_right.max() > 0.5:
        fails.append(f"F-135 12->16->12 is not a round trip "
                     f"(max err {err_right.max():.3f})")
    if err_wrong.mean() < 1.0:
        fails.append("the F-235 ceiling no longer costs anything on F-135 — "
                     "this test's premise needs rechecking")
    return fails


def test_film_base_sentinel_refuses() -> list[str]:
    """FindDmin's 0 means "no valid Dmin". Rendering on it fabricates a frame."""
    fails = []
    lin = np.full((4, 4, 3), 2000.0)
    try:
        dec.f135_rom12_to_rpd12(lin, (159.6, 444.8, 635.5),
                                (879.0, 1250.0, 1386.0), (688, 292, 130),
                                quiet=True, film_base=(3000.0, 0.0, 3000.0))
    except dec.FilmBaseNotFound as e:
        print(f"  film base 0 refused: {str(e)[:72]}…")
        return fails
    fails.append("a film base of 0 (FindDmin's 'not found' sentinel) was "
                 "accepted; it renders a black frame with no warning")
    return fails


def test_film_base_window_is_the_film() -> list[str]:
    """FindDmin must see film — not the leader, not the gate edge.

    Both halves of this were real. The whole of ``strip_cal.bin``'s
    0.29/0.43/0.35 % of ceiling pixels lived in columns 0..45 — CCD pixels
    below the vendor's own window start of 62, where the unit flat-field gain
    is 17-24× — and the whole of ``gold400.bin``'s 6.7 % lived in lines
    0..2105, the clear leader. Neither is over-exposure, and neither may reach
    FindDmin. What must still reach it is film that has genuinely clipped.
    """
    fails = []
    W = dec.PIXELS_PER_LINE
    col0 = dec.film_base_col0()
    if col0 <= 0:
        fails.append("film_base_col0 is 0 for this port's own pixel_offset; "
                     "the vendor's CCD window start is no longer applied")
        return fails

    def strip_with(blown_cols=0):
        lin = np.full((400, W, 3), 2500.0)
        lin[:, :col0] = 4095.0          # gate edge, outside the vendor window
        lin[:40] = 4095.0               # clear leader
        if blown_cols:
            # What over-exposed FILM looks like: highlights on the ceiling in
            # every frame line, not whole lines gone.
            lin[40:, col0:col0 + blown_cols] = 4095.0
        return lin

    lin = strip_with()
    base, win = dec.film_base_codes(lin)
    print(f"  window: columns {win['col0']}.., "
          f"{win['lines_kept']}/{win['lines_total']} lines → base {base}")
    if win["col0"] != col0 or win["lines_kept"] != 360:
        fails.append(f"window is wrong: columns {win['col0']}, "
                     f"{win['lines_kept']} lines (want {col0}, 360)")
    if not all(v == 2500 for v in base):
        fails.append(f"film base {list(base)} is not the film's own 2500 — "
                     f"the leader or the gate edge is still in the histogram")
    try:
        dec.check_film_base(base, lin, window=win)
    except dec.FilmBaseNotFound as e:
        fails.append(f"refused a measurable film base: {e}")

    # …and the refusal still has to fire when the FILM is what clipped.
    lin = strip_with(blown_cols=100)            # 5 % of the film area
    base, win = dec.film_base_codes(lin)
    try:
        dec.check_film_base(base, lin, window=win)
    except dec.FilmBaseNotFound as e:
        print(f"  clipped film still refused: {str(e)[:66]}…")
    else:
        fails.append(f"film clipped over 5 % of its own area was accepted "
                     f"(base {list(base)}); the refusal has been weakened")

    # A saturated line is indistinguishable from leader, so a capture that is
    # mostly saturated must refuse rather than measure a base off the remnant.
    lin = np.full((400, W, 3), 4095.0)
    lin[:100, col0:] = 2500.0
    base, win = dec.film_base_codes(lin)
    try:
        dec.check_film_base(base, lin, window=win)
    except dec.FilmBaseNotFound as e:
        print(f"  mostly-saturated capture refused: {str(e)[:56]}…")
    else:
        fails.append(f"a capture with 100 of 400 lines of film was accepted "
                     f"(base {list(base)}); the line test can be used to "
                     f"discard an over-exposed capture down to its remnant")
    return fails


def main() -> int:
    print("F-135 app render path")
    seg = synthetic_negative()
    print(f"  fixture: {seg.shape} synthetic negative, "
          f"raw14 mean {seg.reshape(-1, 3).mean(axis=0).round(0)}")
    eng = pr._quiet(build_engine)

    fails: list[str] = []
    for fn, args in (
        (test_stage2_alone_is_still_a_negative, (seg, eng)),
        (test_scene_rpd12_inverts, (seg, eng)),
        (test_render_frame_inverts, (seg, eng)),
        (test_rpd_max_round_trip, ()),
        (test_film_base_sentinel_refuses, ()),
        (test_film_base_window_is_the_film, ()),
    ):
        print(f"\n{fn.__name__}")
        fails += fn(*args)

    print()
    if fails:
        for f in fails:
            print(f"FAIL: {f}")
        return 1
    print("PASS: the app inverts the negative, and says so if it cannot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
