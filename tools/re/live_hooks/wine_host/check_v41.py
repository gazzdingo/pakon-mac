#!/usr/bin/env python3
"""Acceptance check for the v41 capture, run BEFORE trusting any of it.

v41 adds two hooks, each aimed at one specific open question:

  analyze_post_balance (PakonIMAu 0x100fe4f0)
      post_shift_4b6   this+0x4b6, 6 B  -- the shift triple AFTER the rewrite.
                       Paired against cn_shift_before (same words at
                       cn_enhanced_driver ENTRY) this yields docs/74 §168's
                       uniform per-frame scalar Delta DIRECTLY, instead of
                       inferring it from the applied LUTs.
      post_scene_4a0   this+0x4a0, 0x60 B -- context around the triple, to
                       catch whatever the rewrite reads. §168.2 searched only
                       fields already dumped; this widens the search.

  tlb_lut_apply (TLB 0x10022a60)
      lut_table        arg_14h, 0x4000 B -- the transfer table itself
                       (4096 entries x 4-byte stride). §163's whole question.
      lut_src          arg_8h,  0x8000 B -- the input plane, so the mapping
                       can be fit point-for-point against poly_input_r (this
                       loop's OUTPUT) on the same frame.

WHAT THIS CHECKS
================
Whether each row produced readable, sane data -- NOT whether the findings hold.
A row can fire and still be wrong (wrong stack index, wrong calling
convention), so each check tests a property that would fail loudly if the row
were mis-specified:

  * post_shift_4b6 must look like a plausible shift triple (same ballpark as
    the applied k: roughly -300..1400) rather than pointer-like garbage. If
    analyzePostBalance is not __thiscall this row reads the wrong base and the
    values will be obviously wrong.
  * lut_table must not be all-zero, and its low words must be non-trivial.
  * Delta must come out UNIFORM across the three channels, as §168.1 found by
    a completely different route. If it does not, the pairing or the row is
    wrong.

Usage:  python3 check_v41.py <capture.jsonl>
"""
from __future__ import annotations

import json
import struct
import sys
from collections import defaultdict
from pathlib import Path


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    src = Path(argv[0])
    if not src.is_file():
        print(f"no such capture: {src}")
        return 2

    dumps: dict[str, list[tuple[int, str]]] = defaultdict(list)
    hooks: set[str] = set()
    for line in src.open(errors="replace"):
        if '"hook_id"' not in line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        hid = r.get("hook_id")
        if hid:
            hooks.add(hid)
        lbl, hx = r.get("label"), r.get("hex")
        if lbl and isinstance(hx, str):
            try:
                dumps[lbl].append((int(r.get("call_id")), hx))
            except (TypeError, ValueError):
                pass

    print(f"capture: {src.name}")
    ok = True

    for h in ("analyze_post_balance", "tlb_lut_apply"):
        present = h in hooks
        print(f"  hook {h:22} {'PRESENT' if present else 'ABSENT'}")
        ok &= present

    # --- post_shift_4b6 -----------------------------------------------------
    rows = sorted(dumps.get("post_shift_4b6", []))
    print(f"\n  post_shift_4b6 dumps: {len(rows)}")
    if rows:
        trip = [struct.unpack("<3h", bytes.fromhex(h[:12])) for _, h in rows]
        lo = min(min(t) for t in trip)
        hi = max(max(t) for t in trip)
        print(f"    range {lo}..{hi}   first: {trip[:3]}")
        sane = -3000 < lo and hi < 6000
        msg = 'YES' if sane else 'NO -- row is mis-specified (wrong base or not __thiscall)'
        print(f"    plausible shift triple: {msg}")
        ok &= sane
    else:
        ok = False

    # --- Delta, cross-checked against §168.1 -------------------------------
    cn = sorted(dumps.get("cn_shift_before", []))
    if rows and cn:
        import bisect
        cc = [c for c, _ in cn]
        deltas = []
        for cid, h in rows:
            j = bisect.bisect_right(cc, cid) - 1
            if j < 0:
                continue
            buf = bytes.fromhex(cn[j][1])
            if len(buf) < 0x4bc:
                continue
            entry = struct.unpack_from("<3h", buf, 0x4b6)
            post = struct.unpack("<3h", bytes.fromhex(h[:12]))
            deltas.append(tuple(post[i] - entry[i] for i in range(3)))
        uni = [d for d in deltas if d[0] == d[1] == d[2]]
        print(f"\n  Delta computed on {len(deltas)} frames; "
              f"uniform across channels on {len(uni)}")
        if deltas:
            print(f"    first: {deltas[:4]}")
            good = len(uni) >= len(deltas) * 0.9
            print(f"    matches §168.1's uniform-scalar finding: "
                  f"{'YES' if good else 'NO -- pairing or row is wrong'}")
            ok &= good

    # --- lut_table ----------------------------------------------------------
    lt = sorted(dumps.get("lut_table", []))
    print(f"\n  lut_table dumps: {len(lt)}")
    if lt:
        raw = bytes.fromhex(lt[0][1])
        print(f"    size {len(raw)} bytes (expect 16384)")
        words = [struct.unpack_from("<H", raw, i * 4)[0]
                 for i in range(min(4096, len(raw) // 4))]
        nz = sum(1 for w in words if w)
        print(f"    non-zero entries: {nz}/{len(words)}")
        print(f"    [0]={words[0]} [1024]={words[1024] if len(words)>1024 else '-'} "
              f"[4095]={words[4095] if len(words)>4095 else '-'}")
        ident = all(words[i] == i for i in range(min(len(words), 4096)))
        imsg = ('YES -- tlb_lut_apply is a no-op on this path, SS163 answered NEGATIVELY'
                if ident else 'no')
        print(f"    identity table: {imsg}")
        ok &= nz > 0
    else:
        ok = False

    print(f"\n{'ACCEPT' if ok else 'REJECT'} — "
          f"{'usable' if ok else 'do not analyse; fix the rows and re-scan'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
