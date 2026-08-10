#!/usr/bin/env python3
"""SRA forward LUT (PakonIMAu.dll) — verified load path only.

This is **not** Shasta ``toneLut``. Shasta builds scene tone LUTs in
``AnsShastaCapabilityImpl::analyze``; these files are
``AnsCommonSraFwdLutDPI`` data used by SRA / DSba.

VERIFIED (image base ``0x10000000``)
====================================

* ``AnsCommonSraFwdLutDPI::readAscii`` @ string ``0x105954a0``
  (``\\Atc\\ansel\\src\\libCommon.ansel\\AnsCommonSraFwdLutDPI.cpp``).
* ASCII markers: ``SRA_NUM_FORWARDLUT =`` @ ``0x10595364``,
  ``SRA_FORWARDLUT[] =`` / ``SRA_FORWARDLUT`` @ ``0x1059537c`` / ``0x1059544c``.
* Shipped names referenced in DLL:
  ``common-sraFwdLut-metric-default.lut`` (``0x10594b08``),
  ``…-rim12.lut`` (``0x105949fc``), ``…-rom12.lut`` (``0x10594a80``).
* ``AnsSraCapabilityImpl::makeSRALUTS`` (``0x10594b78``) **generates**
  further SRA tables in ``libSra.ansel`` — **not** ported; distinct from
  simply loading these files.
* DSba: ``Unable to initialize AnsDSbaParams obj from AnsCommonSraFwdLutDPI``
  (``0x105945f8``).

File shape (shipped ``common-sraFwdLut-metric-default.lut``):
  comment lines, ``SRA_NUM_FORWARDLUT = 4096``, ``SRA_FORWARDLUT =``,
  then one integer per line (index 0‥N-1). Our loader accepts that and
  pads/truncates to 4096.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

SRA_FWD_LUT_SIZE = 4096
SRA_MAKE_LUTS_PORTED = False  # makeSRALUTS @ 0x10594b78 not ported


def load_sra_fwd_lut(path: Path) -> np.ndarray:
    """Load ``AnsCommonSraFwdLutDPI`` ASCII → ``(4096,)`` int32 table.

    Index = RPD code. Does **not** run ``makeSRALUTS``.
    """
    rows: list[int] = []
    declared: int | None = None
    for ln in path.read_text(errors="replace").splitlines():
        s = ln.split("#", 1)[0].strip()
        if not s:
            continue
        if s.upper().startswith("SRA_NUM_FORWARDLUT"):
            _, _, rhs = s.partition("=")
            try:
                declared = int(rhs.strip())
            except ValueError:
                pass
            continue
        if s.upper().startswith("SRA_FORWARDLUT"):
            # header line; optional first value after '='
            _, _, rhs = s.partition("=")
            rhs = rhs.strip()
            if rhs.lstrip("-").isdigit():
                rows.append(int(rhs))
            continue
        if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
            rows.append(int(s))
    n_target = declared if declared and declared > 0 else SRA_FWD_LUT_SIZE
    table = np.zeros(SRA_FWD_LUT_SIZE, dtype=np.int32)
    n = min(len(rows), SRA_FWD_LUT_SIZE, n_target)
    if n:
        table[:n] = rows[:n]
        if n < SRA_FWD_LUT_SIZE:
            table[n:] = rows[n - 1]
    return table


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("lut", type=Path, nargs="?")
    args = ap.parse_args()
    if not args.lut:
        root = Path(
            "/Users/guy/Downloads/Pakon Update 2/fx35install/"
            "program files/Pakon/F-X35 COM SERVER/anselinstalldir/"
            "dataPathItems/common"
        )
        args.lut = root / "common-sraFwdLut-metric-default.lut"
    t = load_sra_fwd_lut(args.lut)
    print(f"{args.lut.name}: len={len(t)} [200]={int(t[200])} [1550]={int(t[1550])}")
    print(f"  SRA_MAKE_LUTS_PORTED={SRA_MAKE_LUTS_PORTED}")


if __name__ == "__main__":
    main()
