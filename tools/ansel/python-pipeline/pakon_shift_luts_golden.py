#!/usr/bin/env python3
"""Golden ``fcn.1006c4f0`` -- the vendor's shift-LUT builder -- against the
REAL PakonIMAu.dll running under Wine.

WHAT IS BEING CHECKED
=====================
``area_image_apply_lut`` (``fcn.100d9340``) is handed three 4096-entry int16
transfer tables. docs/74 §159.2 measured every captured table as exactly
``clip(i + k, 0, 4095)`` -- tier 2, which establishes WHAT is applied but not
what builds it. The builder is ``fcn.1006c4f0``, and its whole body is

    out[i] = master[i + shift]        (int16, i = 0 .. count-1)

over the singleton at ``PakonIMAu+0x6b5f74``, whose ``master`` pointer
(``obj+8``) sits in the middle of a 0x20002-byte allocation, giving signed
index ``-0x8000..0x7fff``.

WHY WINE AND NOT UNICORN
========================
``master`` lives in **uninitialised** ``.data``. It is not in the file image,
no capture dumps it, and it is written by the DLL's own initialisers. Under
Unicorn the table would have to be supplied by hand -- i.e. the answer would be
fabricated input dressed as a result. Wine's real loader runs the real
initialisers, so the bytes that execute and the table they read are both the
vendor's. docs/74 §99 already established Wine as an accepted second engine for
this DLL (byte-identical to Unicorn on all 12 captured ``sba_preference``
calls).

WHAT THIS HARNESS ASSERTS
=========================
1. The master table the DLL built is exactly ``clip(i, 0, 4095)`` over its
   whole valid span, checked at every one of its 65536 entries.
2. For every case, the DLL's three tables equal ``pakon_sba_apply.shift_luts``
   entry-for-entry -- 12288 int16 per case, compared bit-exact, not sampled.

Cases are the real per-frame shift triples measured on hardware (docs/74 §159.3
extremes and the medians either side of them) plus deliberate boundary cases
that drive both clamps.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 -m pakon_shift_luts_golden``
``... python3 -m pakon_shift_luts_golden [dll] [wine_host_dir]``
"""
from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np

from pakon_sba_apply import MASTER_MAX, shift_luts

REPO = Path(__file__).resolve().parents[3]
DEFAULT_HOST_DIR = REPO / "tools" / "re" / "live_hooks" / "wine_host"
HOST_SRC = "shiftlut_host.c"
HOST_EXE = "shiftlut_host.exe"
DEFAULT_DLL = "PakonIMAu.dll"          # resolved inside the host dir
WINEPREFIX = os.path.expanduser("~/wineprefixes/hookcore_test")
COUNT = 4096

# Real per-frame triples from live_hooks_20260819-121153.jsonl
# (area_image_apply_lut, analysis-pass caller 0x100fe87a) plus the extremes
# docs/74 §159.3 reports, plus boundary cases that exercise both clamps.
CASES: list[tuple[int, int, int]] = [
    (0, 0, 0),
    (718, 393, 122),
    (621, 182, -47),
    (448, -21, -250),
    (441, 1, -217),
    (885, 490, 221),
    (1332, 886, 668),          # per-channel maxima, §159.3
    (0, -21, -263),            # per-channel minima, §159.3
    (4095, 4095, 4095),        # top clamp reached at i = 0
    (-4095, -4095, -4095),     # bottom clamp reached at i = 4094
    (4096, -4096, 1),          # one past each clamp
    (28672, -32768, 0),        # the edge of the vendor's own valid domain
]

# The builder indexes `master[i + shift]` with NO range check, and `master`
# only spans -0x8000..0x7fff. So the vendor's own valid domain is
# ``-32768 <= shift`` and ``shift + count - 1 <= 32767``; at count=4096 that
# caps shift at 28672. Outside it the DLL reads past its own allocation and
# returns whatever is there -- checked, and it does: shift=32767 makes the DLL
# disagree with `clip(i + shift)` on 4095 of 4096 entries. The port clamps
# instead, which is a deliberate divergence OUTSIDE the vendor's domain, not a
# mismatch inside it. Measured shifts are 0..1332 (docs/74 §159.3), three
# orders of magnitude inside the limit.
SHIFT_DOMAIN = (-32768, 32767 - COUNT + 1)


def _run_host(host_dir: Path, dll: str, cases: list[tuple[int, int, int]],
              out_bin: Path) -> tuple[np.ndarray, int, list[tuple[int, np.ndarray]]]:
    """Drive the Wine host; return (master, master_lo, [(rc, luts)])."""
    exe = host_dir / HOST_EXE
    src = host_dir / HOST_SRC
    if not src.exists():
        raise RuntimeError(f"missing host source {src}")
    if not exe.exists() or exe.stat().st_mtime < src.stat().st_mtime:
        cc = shutil.which("i686-w64-mingw32-gcc")
        if cc is None:
            raise RuntimeError(
                "i686-w64-mingw32-gcc not found and no up-to-date "
                f"{HOST_EXE}; cannot build the golden engine"
            )
        subprocess.run([cc, "-O2", "-o", str(exe), str(src)], check=True,
                       cwd=str(host_dir))
    wine = shutil.which("wine")
    if wine is None:
        raise RuntimeError("wine not found; cannot run the real DLL")
    if not (host_dir / dll).exists():
        raise RuntimeError(
            f"{dll} not found in {host_dir} -- see wine_host/README.md for the "
            "five vendor DLLs LoadLibrary needs"
        )

    cases_bin = out_bin.with_suffix(".cases")
    with cases_bin.open("wb") as fh:
        fh.write(struct.pack("<i", len(cases)))
        for s in cases:
            fh.write(struct.pack("<3i", *s))

    env = dict(os.environ, WINEPREFIX=WINEPREFIX, WINEDEBUG="-all")
    p = subprocess.run([wine, HOST_EXE, dll, cases_bin.name, out_bin.name],
                       cwd=str(host_dir), env=env, capture_output=True, text=True)
    tail = "\n".join(l for l in (p.stdout + p.stderr).splitlines()
                     if l.strip() and not l.startswith(("\t", "[mvk")))
    if p.returncode != 0 or not out_bin.exists():
        raise RuntimeError(f"host failed (rc={p.returncode}):\n{tail}")
    print(tail)

    blob = out_bin.read_bytes()
    cnt, lo, mn = struct.unpack_from("<iii", blob, 0)
    if cnt != COUNT:
        raise RuntimeError(f"host reported count={cnt}, expected {COUNT}")
    off = 12
    master = np.frombuffer(blob, "<i2", count=mn, offset=off).astype(np.int32)
    off += 2 * mn
    rows = []
    for _ in range(len(cases)):
        (rc,) = struct.unpack_from("<i", blob, off)
        off += 4
        luts = np.frombuffer(blob, "<i2", count=3 * COUNT,
                             offset=off).reshape(3, COUNT).astype(np.int32)
        off += 2 * 3 * COUNT
        rows.append((rc, luts))
    return master, lo, rows


def main(argv: list[str]) -> int:
    host_dir = Path(argv[2]) if len(argv) > 2 else DEFAULT_HOST_DIR
    dll = argv[1] if len(argv) > 1 else DEFAULT_DLL
    out_bin = host_dir / "shiftlut_out.bin"

    try:
        master, lo, rows = _run_host(host_dir, dll, CASES, out_bin)
    except (RuntimeError, subprocess.CalledProcessError) as e:
        # A missing engine is NOT a pass. Say so and fail.
        print(f"cannot run the golden engine: {e}", file=sys.stderr)
        return 2

    failures = 0

    print(f"\nvendor's own valid shift domain at count={COUNT}: "
          f"{SHIFT_DOMAIN[0]}..{SHIFT_DOMAIN[1]} "
          f"(master[i + shift] is unguarded)")

    idx = np.arange(lo, lo + master.size, dtype=np.int32)
    want = np.clip(idx, 0, MASTER_MAX)
    bad = int((master != want).sum())
    print(f"\nmaster table  span {lo}..{lo + master.size - 1}  "
          f"({master.size} entries)")
    print(f"  entries deviating from clip(i, 0, {MASTER_MAX}): {bad}")
    if bad:
        first = int(np.flatnonzero(master != want)[0])
        print(f"  first at i={idx[first]}  dll={master[first]} "
              f"want={want[first]}")
        failures += 1

    print(f"\n{'shifts':>22}  {'rc':>3}  {'entries':>7}  result")
    total = 0
    for (s, (rc, luts)) in zip(CASES, rows):
        port = np.stack([np.asarray(p, dtype=np.int32) for p in shift_luts(s, COUNT)])
        if rc != 0:
            print(f"{str(s):>22}  {rc:>3}  {'-':>7}  FAIL (builder returned {rc})")
            failures += 1
            continue
        diff = int((luts != port).sum())
        total += luts.size
        tag = "OK" if diff == 0 else f"FAIL ({diff} entries differ)"
        if diff:
            failures += 1
        print(f"{str(s):>22}  {rc:>3}  {luts.size:>7}  {tag}")

    print(f"\ncompared {total} int16 entries across {len(CASES)} cases, "
          f"bit-exact, plus {master.size} master entries")
    if failures:
        print(f"{failures} failure(s) — SHIFT_LUTS_PORTED must stay False")
        return 1
    print("all cases bit-exact vs the real DLL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
