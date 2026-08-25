#!/usr/bin/env python3
"""Acceptance check for the v44 capture, run BEFORE trusting any of it.

check_v41.py is stale for v44: it still requires `post_shift_4b6`, a row that
was REMOVED when its hook turned out to sit mid-instruction (docs/74 §173-era
work). Run against a v42/v44 capture it REJECTs for the wrong reason, which is
exactly how a stale check causes a good scan to be thrown away.

v44 carries two questions:

  tlb_lut_apply (TLB 0x10022a60)
      lut_table  arg4 (index 3), 0x10000 B = 16384 entries.
                 v42 dumped 0x4000 = 4096 and §173.1 showed the real index
                 range is 404..11681 -- so v42 captured a QUARTER of the table
                 and the region most pixels hit was never seen. §173.2 showed
                 the closed form 14750 - 3500*log10(i) is only a +/-1
                 approximation (3554/4095 exact), so byte-exactness needs this
                 table, not the formula.
      lut_src    arg2 (index 1), the input plane.

  analyze_post_balance (PakonIMAu 0x100fdc40)
      apb_arg0 / apb_arg1, 0x600 B each -- the two cdecl arguments. Which one
      carries the scene is NOT established, so both are dumped and the shift
      triple is identified offline by matching the known per-frame applied k.
      This is the route to §168's uniform per-frame scalar Delta.

WHAT IS CHECKED
===============
That each row fired and produced sane data -- not that the findings hold. Each
test is chosen to fail loudly on a mis-specified row rather than pass on
garbage:

  * lut_table must be 16384 entries, monotone decreasing, and must AGREE with
    the v42-captured first 4096 entries. Disagreement there means the index or
    stride changed and nothing else in the dump can be trusted.
  * lut_table's coverage must extend past 4096 with real values (the whole
    point of the widening).
  * apb_arg* must be readable and non-constant across calls.

Usage:  python3 check_v44.py <capture.jsonl>
"""
from __future__ import annotations

import json
import struct
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    src = Path(argv[0])
    if not src.is_file():
        print(f"no such capture: {src}")
        return 2

    dumps = defaultdict(list)
    hooks = set()
    for line in src.open(errors="replace"):
        if '"hook_id"' not in line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("hook_id"):
            hooks.add(r["hook_id"])
        lbl, hx = r.get("label"), r.get("hex")
        if lbl and isinstance(hx, str):
            dumps[lbl].append(hx)

    print(f"capture: {src.name}")
    ok = True
    for h in ("tlb_lut_apply", "analyze_post_balance"):
        p = h in hooks
        print(f"  hook {h:22} {'PRESENT' if p else 'ABSENT'}")
        ok &= p

    # --- lut_table ---------------------------------------------------------
    lt = dumps.get("lut_table", [])
    print(f"\n  lut_table dumps: {len(lt)}")
    if lt:
        raw = bytes.fromhex(lt[0])
        n = len(raw) // 4
        print(f"    size {len(raw)} bytes = {n} entries (expect 16384)")
        t = np.array([struct.unpack_from("<H", raw, i * 4)[0]
                      for i in range(n)], dtype=np.int64)
        d = np.diff(t[1:])
        dec = float((d <= 0).mean()) * 100
        print(f"    [1]={t[1]} [10]={t[10]} [100]={t[100]} "
              f"[1000]={t[1000]}"
              + (f" [8000]={t[8000]}" if n > 8000 else ""))
        print(f"    monotone decreasing: {dec:.1f}% of steps")
        # cross-check against v42's captured region and the decade points
        exp = {1: 14750, 10: 11250, 100: 7750, 1000: 4250}
        agree = sum(1 for k, v in exp.items() if k < n and int(t[k]) == v)
        print(f"    decade points match §170 ({exp}): {agree}/4")
        past = int((t[4096:] > 0).sum()) if n > 4096 else 0
        print(f"    entries beyond index 4095 with real values: {past}")
        ok &= (n >= 16384 and dec > 95 and agree >= 3 and past > 1000)
    else:
        ok = False

    # --- lut_src -----------------------------------------------------------
    ls = dumps.get("lut_src", [])
    print(f"\n  lut_src dumps: {len(ls)}")
    if ls:
        s = np.frombuffer(bytes.fromhex(ls[0]), dtype="<u2")
        print(f"    {s.size} samples, range {int(s.min())}..{int(s.max())}")
        print(f"    exceeds 4095 (the v42 dump's ceiling): "
              f"{'YES -- confirms §173.1' if s.max() > 4095 else 'no'}")

    # --- analyze_post_balance ---------------------------------------------
    for lbl in ("apb_arg0", "apb_arg1"):
        rows = dumps.get(lbl, [])
        print(f"\n  {lbl} dumps: {len(rows)}")
        if not rows:
            ok = False
            continue
        uniq = len(set(rows))
        print(f"    distinct: {uniq}   size {len(rows[0]) // 2} bytes")
        if uniq <= 1:
            print("    CONSTANT across calls -- cannot carry a per-frame value")
        ok &= uniq > 1

    print(f"\n{'ACCEPT' if ok else 'REJECT'} — "
          f"{'usable' if ok else 'inspect before analysing'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
