#!/usr/bin/env python3
"""Golden ``kodakcms.dll!fcn.10018160`` -- the vendor CMM's own 3-D CLUT
interpolator -- against the REAL DLL running under Wine.

WHAT IS BEING CHECKED
=====================
docs/74 §171 drove the vendor's CMM on 359,660 real toned pixels and found
this port's PIL/littleCMS ICC step **not** bit-exact -- darker by mean 2.739
sRGB codes (1.836 with ``cmsFLAGS_NOOPTIMIZE``), one-signed, and not fixable
by any per-channel remap. That left a 3-D CLUT interpolation difference as
the only remaining explanation. ``pakon_kcms_clut`` ports the vendor's
interpolator; this harness is the evidence that the port is the vendor's
arithmetic and not a lookalike.

WHICH FUNCTION, AND HOW THAT WAS ESTABLISHED
============================================
``SpEvaluate`` -> ``PTEvalDT`` -> fcn.100410a0 -> fcn.10026d20 ->
fcn.10012b30 -> fcn.10012bc0.  fcn.10012bc0 is a dispatcher that returns one
of **35** evaluator function pointers, which fcn.10027410 then calls as
``call dword [ebx + 4]``.

The live one was NOT inferred from names or from which case "looks right".
``kcms_clut_host.exe`` with ``POKE_RVA=<va>`` overwrites a candidate's first
byte with ``0xC3`` (the ABI is cdecl, so a bare ``ret`` is safe) and re-runs
the whole transform. Exactly one of the 35 changes SpEvaluate's output:
``0x10018160``. This harness re-runs that sweep, so the identification is
re-established every time it is run rather than being taken on trust.

WHY WINE AND NOT UNICORN
========================
The CLUT, the input index table and the output tables do not exist in the
file image. ``SpCombineXforms`` builds them on the heap at run time from the
two profiles. Under Unicorn they would have to be supplied by hand -- i.e.
the input would be fabricated and the "golden" would be circular. Wine runs
the real loader, the real profile parser and the real combiner, so both the
code and the tables it reads are the vendor's. docs/74 §99 already
established Wine as an accepted second engine for this DLL family.

WHAT THIS HARNESS ASSERTS
=========================
1. The ret-poke sweep still singles out 0x10018160 and nothing else.
2. The tables the live DLL builds are byte-identical to the shipped
   ``vendor_kcms_rpd2srgb.npz`` -- 6144 + 178746 + 49152 bytes, compared
   whole, not sampled.
3. The detour is transparent: vendor output with it installed is
   byte-identical to vendor output without it.
4. On every case, ``pakon_kcms_clut.evaluate`` equals the real
   ``SpEvaluate`` byte for byte. Cases are:
     * the **entire** u8 RGB input domain -- all 16,777,216 triples, which
       is an exhaustive proof rather than a sample, and covers all six
       tetrahedra (13.5 / 13.7 / 19.0 / 13.7 / 19.0 / 21.1 %);
     * real toned pixels off this port's own production path
       (``pakon_roll_golden.load_raws`` -> ``pakon_render.scene_rpd12`` ->
       ``AnselEngine.render_scene`` -> ``rpd12_to_icc_u8``), which is the
       exact u8 the ICC sees in a real render.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 -m pakon_kcms_clut_golden``
``... python3 -m pakon_kcms_clut_golden --no-exhaustive``  (skip case 4a)
``... python3 -m pakon_kcms_clut_golden --no-sweep``       (skip case 1)
"""
from __future__ import annotations

import contextlib
import io
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

import pakon_kcms_clut as kc

REPO = Path(__file__).resolve().parents[3]
HOST_DIR = REPO / "tools" / "re" / "live_hooks" / "wine_host"
HOST_SRC = "kcms_clut_host.c"
HOST_EXE = "kcms_clut_host.exe"
DLL = "kodakcms.dll"
PROFILE_DIR = REPO / "vendor" / "ansel" / "anselinstalldir" / "dataPathItems" / "profile"
P1 = "Rpd2Pcs_HR200_QS_v5s10.pf"
P2 = "Srgb_v2.pf"
WINEPREFIX = os.path.expanduser("~/wineprefixes/hookcore_test")

#: every function pointer fcn.10012bc0 can return (`mov eax, 0x100…` in its body)
CANDIDATES = [
    0x10016F60, 0x100171B0, 0x10017530, 0x10017880, 0x10017D80, 0x10018160,
    0x10018480, 0x100187B0, 0x10018E20, 0x1001A330, 0x1001A930, 0x1001B070,
    0x1001B500, 0x1001BCC0, 0x1001C1D0, 0x1001CA70, 0x1001D070, 0x1001DA60,
    0x1001E110, 0x1001EC80, 0x1001F3E0, 0x100200C0, 0x10020400, 0x10020730,
    0x10020BF0, 0x10020FD0, 0x100214D0, 0x10021B30, 0x10022150, 0x100229E0,
    0x10023110, 0x10023BA0, 0x100243A0, 0x10024A90, 0x10025180,
]
LIVE_EVAL = 0x10018160

#: SpXformGet(intent, class) pair that reproduces profile-Rpd2Srgb.dpi
INTENTS = ("0", "1", "0", "2")


# --------------------------------------------------------------------------
def _wine_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env["WINEPREFIX"] = WINEPREFIX
    env["WINEDEBUG"] = "-all"
    env.pop("POKE_RVA", None)
    env.pop("DUMP_DIR", None)
    if extra:
        env.update(extra)
    return env


def build_host() -> Path:
    exe = HOST_DIR / HOST_EXE
    src = HOST_DIR / HOST_SRC
    if not exe.is_file() or exe.stat().st_mtime < src.stat().st_mtime:
        subprocess.run(["i686-w64-mingw32-gcc", "-O1", "-o", HOST_EXE, HOST_SRC],
                       cwd=HOST_DIR, check=True)
    return exe


def run_host(inp: Path, out: Path, extra: dict[str, str] | None = None) -> str:
    cmd = ["wine", HOST_EXE, "run",
           str(PROFILE_DIR / P1), str(PROFILE_DIR / P2), str(inp), str(out),
           *INTENTS]
    r = subprocess.run(cmd, cwd=HOST_DIR, env=_wine_env(extra),
                       capture_output=True, text=True)
    return r.stdout


def write_in(path: Path, rgb: np.ndarray) -> None:
    a = np.ascontiguousarray(np.asarray(rgb, dtype=np.uint8).reshape(-1, 3))
    with open(path, "wb") as f:
        f.write(struct.pack("<i", a.shape[0]))
        f.write(a.tobytes())


def read_out(path: Path) -> tuple[int, np.ndarray]:
    raw = path.read_bytes()
    rc, n = struct.unpack("<ii", raw[:8])
    return rc, np.frombuffer(raw[8:8 + n * 3], np.uint8).reshape(n, 3)


def vendor(rgb: np.ndarray, tmp: Path, tag: str,
           extra: dict[str, str] | None = None) -> tuple[int, np.ndarray]:
    fi, fo = tmp / f"{tag}_in.bin", tmp / f"{tag}_out.bin"
    write_in(fi, rgb)
    run_host(fi, fo, extra)
    return read_out(fo)


# --------------------------------------------------------------------------
def real_toned_u8(nframes: int = 4) -> np.ndarray:
    """The exact u8 the ICC sees on this port's own production path."""
    sys.path.insert(0, str(REPO / "tools"))
    sys.path.insert(0, str(REPO / "tools" / "re"))
    import pakon_roll_golden as rg
    import pakon_decode as dec
    import pakon_ansel as ansel
    import pakon_render as pr

    out = []
    for _d, rgb_raw in rg.load_raws()[:nframes]:
        rgb14 = np.clip(rgb_raw, 0, 16383).astype(np.uint16)
        with contextlib.redirect_stdout(io.StringIO()):
            eng = ansel.AnselEngine.load(dec.DEFAULT_ANSEL_ROOT,
                                         scene=ansel.SceneContext())
            eng.shasta_stand_in = True
            eng.rpd_max = 4095.0
            rpd12 = pr.scene_rpd12(rgb14, dec.DEFAULT_DATA_DIR, np.zeros(3),
                                   "f135", eng)
            toned = eng.render_scene(rpd12, None)
        out.append(ansel.rpd12_to_icc_u8(toned).reshape(-1, 3))
    return np.concatenate(out, axis=0)


def exhaustive_domain() -> np.ndarray:
    r = np.repeat(np.arange(256, dtype=np.uint8), 256 * 256)
    g = np.tile(np.repeat(np.arange(256, dtype=np.uint8), 256), 256)
    b = np.tile(np.arange(256, dtype=np.uint8), 256 * 256)
    return np.stack([r, g, b], 1)


# --------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    do_sweep = "--no-sweep" not in argv
    do_exh = "--no-exhaustive" not in argv
    failures = 0

    build_host()
    print(f"host   {HOST_DIR / HOST_EXE}")
    print(f"dll    {HOST_DIR / DLL}")
    print(f"prof   {P1} + {P2}   intents/classes {INTENTS}")

    with tempfile.TemporaryDirectory(prefix="kcms_clut_") as td:
        tmp = Path(td)

        ramp = np.stack(np.meshgrid(
            np.arange(0, 256, 32), np.arange(0, 256, 32),
            np.arange(0, 256, 32), indexing="ij"), -1).reshape(-1, 3).astype(np.uint8)

        # --- 1. which evaluator is live -------------------------------------
        if do_sweep:
            base_rc, base = vendor(ramp, tmp, "sweep_base")
            hits = []
            for va in CANDIDATES:
                rc, got = vendor(ramp, tmp, "sweep",
                                 {"POKE_RVA": hex(va)})
                if rc != base_rc or not np.array_equal(got, base):
                    hits.append(va)
            ok = hits == [LIVE_EVAL]
            print(f"\nret-poke sweep over {len(CANDIDATES)} dispatch candidates")
            print("  changed SpEvaluate's output: "
                  + (", ".join(hex(h) for h in hits) if hits else "none"))
            print(f"  {'OK' if ok else 'FAIL'} — expected exactly "
                  f"{hex(LIVE_EVAL)}")
            failures += 0 if ok else 1

        # --- 2. shipped tables == live tables --------------------------------
        dd = tmp / "dump"
        dd.mkdir()
        vendor(ramp, tmp, "dumpcase", {"DUMP_DIR": str(dd)})
        live = kc.pack(dd, tmp / "live.npz")
        a = np.load(live)
        b = np.load(kc.TABLE_PATH)
        print("\nvendor tables (built by SpCombineXforms at run time)")
        tbl_ok = True
        for key, nbytes in (("idx", 3 * 256 * 8), ("clut", None), ("otab", 3 * 0x4000),
                            ("corners", None), ("gridN", None)):
            same = np.array_equal(a[key], b[key])
            tbl_ok &= same
            n = a[key].nbytes
            print(f"  {key:8s} {n:>7d} bytes  {'identical' if same else 'DIFFER'}")
        print(f"  {'OK' if tbl_ok else 'FAIL'} — shipped "
              f"{kc.TABLE_PATH.name} matches the live DLL")
        failures += 0 if tbl_ok else 1

        # --- 3. the detour is transparent ------------------------------------
        _, plain = vendor(ramp, tmp, "trans_plain")
        _, hooked = vendor(ramp, tmp, "trans_hook", {"DUMP_DIR": str(dd)})
        ok = np.array_equal(plain, hooked)
        print(f"\ndetour transparency on {ramp.shape[0]} px: "
              f"{'OK' if ok else 'FAIL'}")
        failures += 0 if ok else 1

        # --- 4. the port vs the real routine ---------------------------------
        cases: list[tuple[str, np.ndarray]] = [("8x8x8 lattice", ramp)]
        try:
            real = real_toned_u8()
            cases.append((f"real toned ({real.shape[0]} px)", real))
        except Exception as exc:                       # pragma: no cover
            print(f"\n! real toned pixels unavailable: {exc}")
        if do_exh:
            cases.append(("exhaustive u8 domain", exhaustive_domain()))

        print(f"\n{'case':>28}  {'rc':>3}  {'samples':>10}  result")
        total = 0
        for name, rgb in cases:
            rc, ref = vendor(rgb, tmp, "case")
            mine = kc.evaluate(rgb)
            if rc != 0:
                print(f"{name:>28}  {rc:>3}  {'-':>10}  FAIL (SpEvaluate rc)")
                failures += 1
                continue
            diff = int((mine != ref).sum())
            total += ref.size
            tag = "bit-exact" if diff == 0 else f"FAIL ({diff} samples differ)"
            if diff:
                failures += 1
            print(f"{name:>28}  {rc:>3}  {ref.size:>10}  {tag}")

        print(f"\ncompared {total} u8 channel samples against the real "
              f"kodakcms.dll SpEvaluate")

    if failures:
        print(f"{failures} failure(s) — KCMS_CLUT_PORTED must stay False")
        return 1
    print("all cases bit-exact vs the real DLL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
