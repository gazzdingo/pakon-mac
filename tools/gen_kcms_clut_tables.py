#!/usr/bin/env python3
"""Generate the C and Go copies of the captured vendor CLUT tables.

Writes ``tools/pakon_kcms_clut_tables.h`` and
``tools/ansel/pipeline/kcmsclut/tables.go``.

The tables in ``tools/ansel/python-pipeline/vendor_kcms_rpd2srgb.npz`` are what
``kodakcms.dll``'s ``SpCombineXforms`` builds on the heap at run time for the
``Rpd2Pcs_HR200_QS_v5s10.pf`` -> ``Srgb_v2.pf`` pair; they do not exist in any
file image and are captured by
``tools/re/live_hooks/wine_host/kcms_clut_host.c``.  See docs/74 §176 and
``tools/ansel/python-pipeline/pakon_kcms_clut.py``.

Why generated source rather than loading the npz at run time
------------------------------------------------------------
``pakon_pipeline_cli.c`` and ``pakon_raw_decoder.c`` are single-translation-unit
standalone C programs with no data-path resolution of their own -- the only
data paths they have are absolute vendor paths hardcoded in ``main``.  The Go
pipeline builds to a single binary and a dylib that the app loads.  Baking the
tables into the image gives both no new runtime failure mode, no new file to
ship, and no zlib/npz parser to write in either language.  The cost is that
this repo carries ~1.1 MB of generated source for ~234 KB of table, and that
both copies must be regenerated whenever the npz changes -- which is why the
npz's md5 is recorded in each and re-checked here.

Usage
-----
    python3 tools/gen_kcms_clut_tables.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
NPZ = REPO / "tools" / "ansel" / "python-pipeline" / "vendor_kcms_rpd2srgb.npz"
OUT = REPO / "tools" / "pakon_kcms_clut_tables.h"
OUT_GO = REPO / "tools" / "ansel" / "pipeline" / "kcmsclut" / "tables.go"

#: md5 of the npz these tables were generated from (docs/74 §176).
EXPECT_MD5 = "28d5812832f1e5a0a4af4139732c722c"


def rows(vals, per_line: int) -> str:
    out = []
    for i in range(0, len(vals), per_line):
        out.append("    " + ",".join(str(v) for v in vals[i:i + per_line]) + ",")
    return "\n".join(out)


def rows_go(vals, per_line: int, indent: str) -> str:
    """Same, in the form ``gofmt`` produces — so ``gofmt -l`` stays quiet on
    the generated file and nobody's editor can silently reformat it out from
    under the md5 the harness checks."""
    out = []
    for i in range(0, len(vals), per_line):
        out.append(indent + ", ".join(str(v) for v in vals[i:i + per_line]) + ",")
    return "\n".join(out)


def main() -> int:
    md5 = hashlib.md5(NPZ.read_bytes()).hexdigest()
    if md5 != EXPECT_MD5:
        print(f"npz md5 {md5} != expected {EXPECT_MD5} -- refusing to generate "
              f"tables from an unverified capture", file=sys.stderr)
        return 1

    z = np.load(NPZ)
    idx = z["idx"].astype(np.int64)          # (3, 256, 2): byte offset, weight
    clut = z["clut"].astype(np.int64)        # 31^3 * 3 u16, output-interleaved
    otab = z["otab"]                         # (3, 16384) u8
    corners = z["corners"].astype(np.int64)
    gridN = int(z["gridN"])
    oB, oG, oGB, oR, oRB, oRG, oRGB = (int(v) for v in corners)

    assert idx.shape == (3, 256, 2) and otab.shape == (3, 0x4000)
    assert clut.size == gridN ** 3 * 3
    assert clut.min() >= 0 and clut.max() <= 0xFFFF

    w = []
    w.append("/*")
    w.append(" * pakon_kcms_clut_tables.h -- GENERATED, DO NOT EDIT BY HAND.")
    w.append(" *")
    w.append(" * Regenerate with: python3 tools/gen_kcms_clut_tables.py")
    w.append(" *")
    w.append(" * Source: tools/ansel/python-pipeline/vendor_kcms_rpd2srgb.npz")
    w.append(f" *         md5 {EXPECT_MD5}")
    w.append(" *")
    w.append(" * These are the tables kodakcms.dll (md5")
    w.append(" * e4c8064a9dd3c3a5541d74b00a730e53) builds at run time via")
    w.append(" * SpCombineXforms for the profile pair")
    w.append(" * Rpd2Pcs_HR200_QS_v5s10.pf (md5 c1d4f3bba8f06f3427ccfaff5c30b559) ->")
    w.append(" * Srgb_v2.pf (md5 95bd003685a81450184af6aaf1d0e31c), captured by")
    w.append(" * tools/re/live_hooks/wine_host/kcms_clut_host.c and verified")
    w.append(" * byte-identical to the live DLL's own by")
    w.append(" * tools/ansel/python-pipeline/pakon_kcms_clut_golden.py case 2.")
    w.append(" *")
    w.append(" * Layout, per fcn.10018160 (docs/74 §176):")
    w.append(" *   kcms_idx   grid+0x8c, 3 x 256 records of {i32 byte offset, i32 weight}")
    w.append(f" *   kcms_clut  {gridN}^3 grid of u16, output-interleaved, stride 6 bytes")
    w.append(" *   kcms_otab  grid+0x154, 3 x 16384 u8 output transfer tables")
    w.append(" */")
    w.append("#ifndef PAKON_KCMS_CLUT_TABLES_H")
    w.append("#define PAKON_KCMS_CLUT_TABLES_H")
    w.append("")
    w.append("#include <stdint.h>")
    w.append("")
    w.append(f'#define KCMS_CLUT_NPZ_MD5   "{EXPECT_MD5}"')
    w.append(f"#define KCMS_CLUT_GRID_N    {gridN}")
    w.append(f"#define KCMS_CLUT_WORDS     {clut.size}")
    w.append("#define KCMS_OTAB_ENTRIES   16384")
    w.append("")
    w.append("/* Intermediate-corner byte offsets into the CLUT (grid+0x74..0x8c). */")
    for name, val in (("OFF_B", oB), ("OFF_G", oG), ("OFF_GB", oGB),
                      ("OFF_R", oR), ("OFF_RB", oRB), ("OFF_RG", oRG),
                      ("OFF_RGB", oRGB)):
        w.append(f"#define KCMS_{name:<7s} {val}")
    w.append("")
    w.append("/* [channel][code][0] = byte offset into the CLUT, [1] = weight 0..65535. */")
    w.append("static const int32_t kcms_idx[3][256][2] = {")
    for c in range(3):
        w.append("  {")
        w.append(rows([f"{{{int(o)},{int(k)}}}" for o, k in idx[c]], 4))
        w.append("  },")
    w.append("};")
    w.append("")
    w.append(f"static const uint16_t kcms_clut[{clut.size}] = {{")
    w.append(rows(clut.tolist(), 24))
    w.append("};")
    w.append("")
    w.append("static const uint8_t kcms_otab[3][16384] = {")
    for c in range(3):
        w.append("  {")
        w.append(rows(otab[c].tolist(), 32))
        w.append("  },")
    w.append("};")
    w.append("")
    w.append("#endif /* PAKON_KCMS_CLUT_TABLES_H */")

    OUT.write_text("\n".join(w) + "\n")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes) from {NPZ.name} md5 {md5}")

    # ---------------------------------------------------------------- Go ---
    g = []
    g.append("// Code generated by tools/gen_kcms_clut_tables.py. DO NOT EDIT.")
    g.append("//")
    g.append("// Source: tools/ansel/python-pipeline/vendor_kcms_rpd2srgb.npz")
    g.append(f"//         md5 {EXPECT_MD5}")
    g.append("//")
    g.append("// The tables kodakcms.dll (md5 e4c8064a9dd3c3a5541d74b00a730e53)")
    g.append("// builds at run time via SpCombineXforms for")
    g.append("// Rpd2Pcs_HR200_QS_v5s10.pf -> Srgb_v2.pf, captured by")
    g.append("// tools/re/live_hooks/wine_host/kcms_clut_host.c and checked")
    g.append("// byte-for-byte against the live DLL's own by")
    g.append("// tools/ansel/python-pipeline/pakon_kcms_clut_golden.py case 2.")
    g.append("")
    g.append("package kcmsclut")
    g.append("")
    g.append(f'// NpzMD5 is the capture these tables came from.')
    g.append(f'const NpzMD5 = "{EXPECT_MD5}"')
    g.append("")
    g.append("const (")
    g.append(f"\tGridN     = {gridN} // CLUT is GridN^3 nodes")
    g.append(f"\tClutWords = {clut.size}")
    g.append("\tOtabSize  = 16384")
    g.append(")")
    g.append("")
    g.append("// Intermediate-corner byte offsets into the CLUT (grid+0x74..0x8c).")
    g.append("const (")
    for name, val in (("offB", oB), ("offG", oG), ("offGB", oGB),
                      ("offR", oR), ("offRB", oRB), ("offRG", oRG),
                      ("offRGB", oRGB)):
        g.append(f"\t{name:<6s} = {val}")
    g.append(")")
    g.append("")
    g.append("// idxOff and idxWeight are the precomputed input table at grid+0x8c,")
    g.append("// split into its two int32 fields: a byte offset into the CLUT and a")
    g.append("// 0..65535 weight. Split rather than [3][256][2]int32 so the hot loop")
    g.append("// reads one value per lookup instead of a two-word record.")
    for varname, col in (("idxOff", 0), ("idxWeight", 1)):
        g.append(f"var {varname} = [3][256]int32{{")
        for c in range(3):
            g.append("\t{")
            g.append(rows_go(idx[c, :, col].tolist(), 8, "\t\t"))
            g.append("\t},")
        g.append("}")
        g.append("")
    g.append(f"var clut = [{clut.size}]uint16{{")
    g.append(rows_go(clut.tolist(), 16, "\t"))
    g.append("}")
    g.append("")
    g.append("var otab = [3][16384]uint8{")
    for c in range(3):
        g.append("\t{")
        g.append(rows_go(otab[c].tolist(), 24, "\t\t"))
        g.append("\t},")
    g.append("}")

    OUT_GO.parent.mkdir(parents=True, exist_ok=True)
    OUT_GO.write_text("\n".join(g) + "\n")
    print(f"wrote {OUT_GO} ({OUT_GO.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
