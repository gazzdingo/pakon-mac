#!/usr/bin/env python3
r"""Phase 6 acceptance test (Python-only pass) — old stand-in vs the real
``analyzeAutoTone`` chain, on one real local frame.

    PYTHONPATH=tools/ansel/python-pipeline python3 tools/measure_python_autotone.py \
        captures/out_test/frames/08_raw14.tiff /tmp/some/scratch/dir

WHY THIS EXISTS. docs/66's Phase 6 hard acceptance criterion needs a real
before/after render of the SAME frame through the OLD two-anchor stand-in
(``pakon_ansel.shasta_two_anchor_tone``) and the NEW real chain
(``pakon_ansel.real_auto_tone``, which assembles the six already
Unicorn-verified subsystems via ``pakon_autotone.analyze_auto_tone``). This
script renders both, writes each to a tap-dir in the SAME format
``tools/ansel/pipeline/taps.go`` uses (manifest.json + one array file per
stage), and ``tools/measure_shadow_clip.py --compare`` reads those tap-dirs
to compute the shadow-clip delta — reusing that script rather than
duplicating its percentage math, per docs/66's own instruction to reuse/
extend existing measurement tooling.

This pass is Python-only (the app's ``PAKON_COLOUR_ENGINE=python`` fallback
path, not the Go dylib the app normally renders through) — see this script's
own README-equivalent note in docs/66 Phase 6 for why, and
``tools/pakon_render.py``'s ``colour_engine()``/``_render_colour_python`` for
the exact mechanism the owner can point the running app at.

CAPTURES. This script reads one frame under captures/ (never writes there,
never commits it, never describes its contents — this project's hard rule).
The tap-dirs it writes go wherever the caller points ``out_dir`` — point that
at a scratch location outside captures/ and outside the repo's tracked tree.

The frame is read with a tiny hand-rolled reader
(``read_raw14_tiff`` below) because PIL silently misreads this project's own
16-bit-per-sample TIFFs as 8-bit RGB (confirmed empirically: same file, PIL
reports mode "RGB" / uint8 / max value 67, i.e. wrong by orders of magnitude)
— this project's own writer (``pakon_color.write_tiff``) is a minimal
untagged baseline TIFF, and this is a minimal matching reader, not a general
TIFF library replacement.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools" / "ansel" / "python-pipeline"))


def read_raw14_tiff(path: str) -> np.ndarray:
    """Minimal baseline-TIFF reader for this project's own write_tiff()
    output: little-endian classic TIFF, single IFD, single strip, 16-bit
    samples, uncompressed. See module docstring for why this exists instead
    of PIL.
    """
    data = Path(path).read_bytes()
    if data[0:2] != b"II":
        raise ValueError(f"{path}: not little-endian classic TIFF")
    magic, = struct.unpack_from("<H", data, 2)
    if magic != 42:
        raise ValueError(f"{path}: not classic TIFF (magic={magic})")
    ifd_off, = struct.unpack_from("<I", data, 4)
    n_entries, = struct.unpack_from("<H", data, ifd_off)
    tags: dict[int, int | list[int]] = {}
    for i in range(n_entries):
        off = ifd_off + 2 + i * 12
        tag, typ, cnt = struct.unpack_from("<HHI", data, off)
        raw = data[off + 8:off + 12]
        if typ == 3:  # SHORT
            if cnt == 1:
                val = struct.unpack_from("<H", raw, 0)[0]
            else:
                voff, = struct.unpack_from("<I", raw, 0)
                val = list(struct.unpack_from(f"<{cnt}H", data, voff))
        elif typ == 4:  # LONG
            if cnt == 1:
                val = struct.unpack_from("<I", raw, 0)[0]
            else:
                voff, = struct.unpack_from("<I", raw, 0)
                val = list(struct.unpack_from(f"<{cnt}I", data, voff))
        else:
            raise ValueError(f"{path}: unsupported TIFF field type {typ} "
                              f"for tag {tag}")
        tags[tag] = val
    width = tags[256]
    height = tags[257]
    bits = tags[258]
    samples = tags[277]
    strip_off = tags[273]
    strip_bytes = tags[279]
    strip_off = strip_off[0] if isinstance(strip_off, list) else strip_off
    strip_bytes = (strip_bytes[0] if isinstance(strip_bytes, list)
                   else strip_bytes)
    bps = bits[0] if isinstance(bits, list) else bits
    if bps != 16:
        raise ValueError(f"{path}: expected 16 bits/sample, got {bps}")
    raw = data[strip_off:strip_off + strip_bytes]
    arr = np.frombuffer(raw, dtype="<u2")
    expect = width * height * samples
    if arr.size != expect:
        raise ValueError(f"{path}: strip has {arr.size} u16 samples, "
                          f"expected {expect} ({width}x{height}x{samples})")
    return arr.reshape(height, width, samples).astype(np.float64)


def write_tap_dir(out_dir: Path, *, height: int, width: int,
                  rpd12_toned: np.ndarray, icc_u8: np.ndarray,
                  engine_label: str) -> None:
    """Same format tools/ansel/pipeline/taps.go writes: manifest.json +
    <name>.f64 (little-endian float64, (h,w,3)) / <name>.u8 (uint8, (h,w,3)),
    so tools/measure_shadow_clip.py reads either engine's output identically.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    np.ascontiguousarray(rpd12_toned, dtype="<f8").tofile(out_dir / "shasta.f64")
    np.ascontiguousarray(rpd12_toned, dtype="<f8").tofile(out_dir / "ansel.f64")
    np.ascontiguousarray(icc_u8, dtype=np.uint8).tofile(out_dir / "icc.u8")
    manifest = {
        "engine": engine_label,
        "height": height,
        "width": width,
        "taps": ["shasta", "ansel", "icc"],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1))


def render_both(tiff_path: str, out_root: Path) -> tuple[Path, Path]:
    import pakon_ansel as ansel
    import pakon_color as pc
    import pakon_decode as dec
    import pakon_shasta as shasta_mod

    raw14 = read_raw14_tiff(tiff_path)
    height, width = raw14.shape[0], raw14.shape[1]

    film_path = "ColNeg"
    film_class = pc.film_class_for_path(film_path)
    dec.check_film_class(film_class, "f135")
    coeffs, _ = pc.load_matrix_eeprom(film_class=film_class)
    coeffs = [pc.f32(v) for v in coeffs]
    poly = pc.poly_hwc(raw14, coeffs, film_class=film_class).astype(np.float64)

    scene = ansel.scene_from_filmstock(path=film_path)
    engine = ansel.AnselEngine.load(ansel.DEFAULT_ANSEL_ROOT, scene=scene)
    engine.rpd_max = ansel.SHASTA_MAX
    engine.shasta_stand_in = True

    ped = (coeffs[9], coeffs[19], coeffs[29])
    # film_base=None: measure from THIS frame (there is no roll context here,
    # only one exported frame) -- consistent for both renders below, which is
    # what a controlled before/after comparison needs; not a claim this is
    # the roll's true film base (docs/decode's own film_base docstring is
    # explicit that per-frame measurement is a stand-in for that).
    inv = dec.f135_rom12_to_rpd12(
        poly, ped, engine.sba.fpo, engine.setshifts_out,
        quiet=True, film_base=None, capture=None,
    )
    inv16 = inv.astype(np.int16)

    print(f"rendering OLD (two-anchor stand-in) ...", file=sys.stderr)
    # Force the flag rather than assert it. The original assert fired before
    # the script could render anything once AUTO_TONE_PORTED's on-disk value
    # legitimately became True (the owner's own local flip for visual
    # comparison, docs/66 Phase 6.2) -- a real bug in the instrument, not in
    # the port. Forcing it keeps the OLD/NEW comparison controlled regardless
    # of the on-disk value; the module attribute is restored below and the
    # file on disk is never edited by this script.
    saved_auto_tone = shasta_mod.AUTO_TONE_PORTED
    shasta_mod.AUTO_TONE_PORTED = False
    old_toned = engine.render_scene(inv16)
    old_icc = engine.to_srgb(old_toned)
    old_dir = out_root / "old_standin"
    write_tap_dir(old_dir, height=height, width=width, rpd12_toned=old_toned,
                 icc_u8=old_icc, engine_label="python-old-standin")
    print(f"  wrote {old_dir}", file=sys.stderr)

    print(f"rendering NEW (real analyzeAutoTone chain) ...", file=sys.stderr)
    shasta_mod.AUTO_TONE_PORTED = True
    try:
        new_toned = engine.render_scene(inv16)
    finally:
        shasta_mod.AUTO_TONE_PORTED = saved_auto_tone
    new_icc = engine.to_srgb(new_toned)
    new_dir = out_root / "new_realport"
    write_tap_dir(new_dir, height=height, width=width, rpd12_toned=new_toned,
                 icc_u8=new_icc, engine_label="python-new-realport")
    print(f"  wrote {new_dir}", file=sys.stderr)

    return old_dir, new_dir


def main() -> None:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <raw14.tiff> <out_dir>", file=sys.stderr)
        raise SystemExit(2)
    tiff_path, out_dir = sys.argv[1], Path(sys.argv[2])
    old_dir, new_dir = render_both(tiff_path, out_dir)
    print()
    print(f"old_dir={old_dir}")
    print(f"new_dir={new_dir}")
    print()
    print("Now run:")
    print(f"  python3 tools/measure_shadow_clip.py --compare {old_dir} {new_dir}")


if __name__ == "__main__":
    main()
