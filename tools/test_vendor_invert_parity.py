#!/usr/bin/env python3
"""Go's generated vendor-inversion table vs the Python engine's own.

WHY THIS EXISTS
===============
docs/74 §182.3 records that the Go and Python engines diverge upstream of
tone, and §191/§193 record that Go is the DEFAULT, product render path. So
"Python has the vendor inversion and Go does not" is not a cosmetic gap: it
means the product path cannot reach the single largest colour improvement this
project has found (59.14 MAE -> 23.59, docs/74 §170-§175).

The table now crosses into Go as generated source
(``tools/gen_vendor_invert_table.py`` -> ``vendorinvert/tables.go``), the same
shape §179 used for the KCMS CLUT. Generated source can go stale silently, so
this test does two things a Go-only test cannot:

  1. parses the ACTUAL Go source and compares it entry-for-entry against what
     ``pakon_render._vendor_invert_lut()`` returns -- the function the Python
     engine really calls, not a re-read of the .npy; and
  2. re-runs the generator's own ``--check``, so a hand-edit of tables.go is
     caught even if it happens to still parse.

Usage:
    python3 tools/test_vendor_invert_parity.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
GO = ROOT / "tools" / "ansel" / "pipeline" / "vendorinvert" / "tables.go"
sys.path.insert(0, str(ROOT / "tools"))


def parse_go_table(path: Path) -> np.ndarray:
    """Pull the uint16 literals out of the generated Go array."""
    src = path.read_text()
    m = re.search(r"var Table = \[Entries\]uint16\{(.*?)\n\}", src, re.S)
    if not m:
        raise SystemExit("could not find `var Table` in the generated Go source")
    vals = [int(v) for v in re.findall(r"(\d+),", m.group(1))]
    return np.asarray(vals, dtype=np.int64)


def main() -> int:
    fails: list[str] = []

    # (2) first, because a stale file makes (1) meaningless.
    p = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "gen_vendor_invert_table.py"),
         "--check"],
        capture_output=True, text=True, cwd=str(ROOT))
    print(f"  generator --check: {p.stdout.strip() or p.stderr.strip()}")
    if p.returncode != 0:
        fails.append("tables.go is stale or hand-edited")

    import pakon_render as pr  # noqa: E402

    py = np.asarray(pr._vendor_invert_lut(), dtype=np.int64)
    go = parse_go_table(GO)

    print(f"  python _vendor_invert_lut(): {py.size} entries, "
          f"{py.min()}..{py.max()}")
    print(f"  go vendorinvert.Table:       {go.size} entries, "
          f"{go.min()}..{go.max()}")

    if py.size != go.size:
        fails.append(f"length differs: python {py.size} vs go {go.size}")
    else:
        diff = np.flatnonzero(py != go)
        if diff.size:
            i = int(diff[0])
            fails.append(
                f"{diff.size} entries differ; first at {i}: "
                f"python {py[i]} vs go {go[i]}")
        else:
            print(f"  all {py.size} entries identical")

    # A guard against the substitution §173.2 warns about: if Python has
    # silently fallen back to the closed form, the two would still agree with
    # each other but both be wrong. The real table is NOT the closed form.
    idx = np.arange(1, py.size, dtype=np.float64)
    closed = np.clip(np.rint(14750.0 - 3500.0 * np.log10(idx)), 0, 16383)
    exact = int((py[1:] == closed).sum())
    pct = 100.0 * exact / (py.size - 1)
    print(f"  vs closed form: {exact}/{py.size - 1} exact ({pct:.2f} %)")
    if pct > 99.0:
        fails.append(
            f"python's table is {pct:.2f} % identical to the closed form — it "
            f"has probably fallen back to the approximation instead of "
            f"loading the captured table (docs/74 §173.2)")

    print()
    if fails:
        for f in fails:
            print(f"FAIL: {f}")
        return 1
    print("PASS: the Go engine's inversion table is the Python engine's, "
          "entry for entry.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
