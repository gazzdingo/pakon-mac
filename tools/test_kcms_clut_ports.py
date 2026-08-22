#!/usr/bin/env python3
"""Golden-by-transitivity harness for the C and Go ports of the vendor CLUT.

WHAT IS BEING CHECKED
=====================
``tools/pakon_kcms_clut_c.c`` and ``tools/ansel/pipeline/kcmsclut/`` are
transcriptions of ``tools/ansel/python-pipeline/pakon_kcms_clut.py``, which
``pakon_kcms_clut_golden.py`` proves bit-exact against the REAL
``kodakcms.dll`` ``fcn.10018160`` over the entire u8 RGB input domain --
16,777,216 triples, 50,331,648 channel samples, zero differences (docs/74
§176). This harness diffs both ports against that Python over the same entire
domain, so a pass here plus a pass there is bit-exactness against the vendor,
by transitivity.

It is NOT a substitute for the golden harness. Only ``pakon_kcms_clut_golden.py``
touches the DLL; if the tables or the reference ever change, that is the one
that has to be re-run. What this adds is that the two other pipelines cannot
silently drift away from the reference.

Both ports read tables generated from the same npz the Python loads
(``tools/gen_kcms_clut_tables.py``), and this harness re-runs the generator and
checks the generated files are unchanged, so a pass cannot be obtained by
hand-editing a port's copy of the tables.

Cases, per port
---------------
1. The port's own smoke self-check (the C's ``kcms_sar14`` really is floor;
   Go's ``>>`` is arithmetic by language definition, so there is nothing to
   check there).
2. All six tetrahedra are visited over the domain, with counts. The six-way
   weight-ordering branch is where a transcription is most likely to go wrong,
   and its tie rules are asymmetric.
3. Exhaustive: all 16,777,216 u8 RGB triples, port vs Python, byte for byte.

Usage
-----
    python3 tools/test_kcms_clut_ports.py
    python3 tools/test_kcms_clut_ports.py --quick     # 4M random triples
    python3 tools/test_kcms_clut_ports.py --c-only
    python3 tools/test_kcms_clut_ports.py --go-only
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
C_SRC = REPO / "tools" / "test_kcms_clut_c.c"
C_HDR = REPO / "tools" / "pakon_kcms_clut_tables.h"
GO_DIR = REPO / "tools" / "ansel" / "pipeline"
GO_TBL = GO_DIR / "kcmsclut" / "tables.go"
NPZ = REPO / "tools" / "ansel" / "python-pipeline" / "vendor_kcms_rpd2srgb.npz"
NPZ_MD5 = "28d5812832f1e5a0a4af4139732c722c"

sys.path.insert(0, str(REPO / "tools" / "ansel" / "python-pipeline"))
import pakon_kcms_clut as kc  # noqa: E402

#: triples per compare chunk -- the exhaustive case is 50 MB of output
CHUNK = 1 << 22
TOTAL = 1 << 24

#: what pakon_kcms_clut_golden.py reports for the same six branches, so a
#: transcription that lands in the wrong tetrahedron shows up as a shape
#: change and not only as a byte diff.
GOLDEN_TETRA_PCT = (13.5, 13.7, 19.0, 13.7, 19.0, 21.1)


def domain_chunk(start: int, n: int) -> np.ndarray:
    """Triples [start, start+n) of the r-slowest / b-fastest u8 domain."""
    i = np.arange(start, start + n, dtype=np.int64)
    return np.stack([(i >> 16) & 0xFF, (i >> 8) & 0xFF, i & 0xFF],
                    axis=1).astype(np.uint8)


def check_tetra(stderr: str) -> bool:
    counts = [int(line.split()[3]) for line in stderr.strip().splitlines()
              if line.startswith("tetra")]
    if len(counts) != 6 or sum(counts) != TOTAL or not all(counts):
        return False
    pct = [100.0 * c / TOTAL for c in counts]
    return all(abs(p - g) < 0.1 for p, g in zip(pct, GOLDEN_TETRA_PCT))


def compare_exhaustive(cmd: list[str], label: str) -> int:
    """Stream the port's whole-domain output and diff it against the Python."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, cwd=GO_DIR)
    diff = done = worst = 0
    while done < TOTAL:
        n = min(CHUNK, TOTAL - done)
        raw = proc.stdout.read(n * 3)
        if len(raw) != n * 3:
            print(f"{label}: FAIL — produced {done * 3 + len(raw)} of "
                  f"{TOTAL * 3} bytes")
            proc.stdout.close()
            proc.wait()
            return 1
        mine = np.frombuffer(raw, np.uint8).reshape(n, 3)
        ref = kc.evaluate(domain_chunk(done, n))
        d = mine != ref
        if d.any():
            diff += int(d.sum())
            worst = max(worst, int(np.abs(
                mine.astype(np.int16) - ref.astype(np.int16)).max()))
        done += n
    proc.stdout.close()
    proc.wait()
    tag = "bit-exact" if diff == 0 else f"FAIL ({diff} differ, max |d| {worst})"
    print(f"  {'exhaustive u8 domain':<24} {TOTAL * 3:>10} samples  {tag}")
    return 0 if diff == 0 else 1


def compare_random(cmd: list[str], label: str) -> int:
    rng = np.random.default_rng(0xC107)
    rgb = rng.integers(0, 256, size=(1 << 22, 3), dtype=np.uint8)
    blob = np.int32(rgb.shape[0]).tobytes() + rgb.tobytes()
    got = subprocess.run(cmd, input=blob, capture_output=True, cwd=GO_DIR).stdout
    if len(got) != rgb.size:
        print(f"{label}: FAIL — produced {len(got)} of {rgb.size} bytes")
        return 1
    mine = np.frombuffer(got, np.uint8).reshape(-1, 3)
    ref = kc.evaluate(rgb)
    diff = int((mine != ref).sum())
    print(f"  {'random 4194304 triples':<24} {ref.size:>10} samples  "
          f"{'bit-exact' if diff == 0 else f'FAIL ({diff} differ)'}")
    return 0 if diff == 0 else 1


def main(argv: list[str]) -> int:
    quick = "--quick" in argv
    do_c = "--go-only" not in argv
    do_go = "--c-only" not in argv
    compare = compare_random if quick else compare_exhaustive
    failures = 0

    md5 = hashlib.md5(NPZ.read_bytes()).hexdigest()
    print(f"tables {NPZ.name} md5 {md5} "
          f"{'OK' if md5 == NPZ_MD5 else 'MISMATCH — expected ' + NPZ_MD5}")
    failures += 0 if md5 == NPZ_MD5 else 1

    # --- the generated tables are what the generator produces ---------------
    before = {p: hashlib.md5(p.read_bytes()).hexdigest() for p in (C_HDR, GO_TBL)}
    gen = subprocess.run([sys.executable,
                          str(REPO / "tools" / "gen_kcms_clut_tables.py")],
                         capture_output=True, text=True)
    if gen.returncode != 0:
        print("table regeneration FAILED:", gen.stderr.strip())
        failures += 1
    else:
        for p, was in before.items():
            now = hashlib.md5(p.read_bytes()).hexdigest()
            ok = was == now
            print(f"{p.name:<28} md5 {now} — regenerating from the npz "
                  f"{'reproduces it' if ok else 'CHANGED IT (was ' + was + ')'}")
            failures += 0 if ok else 1

    with tempfile.TemporaryDirectory(prefix="kcms_ports_") as td:
        tmp = Path(td)

        # ------------------------------------------------------------- C ---
        if do_c:
            print("\n=== C: tools/pakon_kcms_clut_c.c ===")
            exe = tmp / "test_kcms_clut_c"
            subprocess.run(["cc", "-O2", "-Wall", "-Wextra", "-o", str(exe),
                            str(C_SRC), "-lm"], cwd=REPO / "tools", check=True)
            demo = subprocess.run([str(exe), "--demo"], capture_output=True,
                                  text=True)
            print(demo.stdout.rstrip())
            failures += 0 if demo.returncode == 0 else 1
            tet = subprocess.run([str(exe), "--tetra"], capture_output=True,
                                 text=True)
            print(tet.stderr.rstrip())
            ok = check_tetra(tet.stderr)
            print(f"  all six tetrahedra visited, in the golden proportions: "
                  f"{'OK' if ok else 'FAIL'}")
            failures += 0 if ok else 1
            failures += compare([str(exe),
                                 "--stream" if quick else "--exhaustive"], "C")

        # ------------------------------------------------------------ Go ---
        if do_go:
            print("\n=== Go: tools/ansel/pipeline/kcmsclut ===")
            exe = tmp / "kcmsdump"
            subprocess.run(["go", "build", "-o", str(exe), "./cmd/kcmsdump"],
                           cwd=GO_DIR, check=True)
            tet = subprocess.run([str(exe), "--tetra"], capture_output=True,
                                 text=True, cwd=GO_DIR)
            print(tet.stderr.rstrip())
            ok = check_tetra(tet.stderr)
            print(f"  all six tetrahedra visited, in the golden proportions: "
                  f"{'OK' if ok else 'FAIL'}")
            failures += 0 if ok else 1
            failures += compare([str(exe),
                                 "--stream" if quick else "--exhaustive"], "Go")

    print()
    if failures:
        print(f"{failures} failure(s)")
        return 1
    print("the C and Go ports match pakon_kcms_clut.py byte for byte; that "
          "module is bit-exact against the real kodakcms.dll "
          "(pakon_kcms_clut_golden.py)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
