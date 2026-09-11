#!/usr/bin/env python3
"""Read the ICC source/dest max from a v35 capture -- and verify it first.

docs/74 §135: the washed-out defect reduces to one unknown. ImaICCEffectOp
(0x1016ede0) loads

    0x1016ee84   fld qword [esi + 0x120]     ; dest max
    0x1016ee93   fld qword [esi + 0x118]     ; source max

as doubles. If source max is 4095, this port's `x255/4095` pre-ICC encode is
right and a pipeline stage is MISSING between tone and ICC. If it is the paper
range (1200..2000) or 32767, the ENCODE is wrong and no stage is missing.

The `icc_scales` row has never fired before this capture, exactly as `bai_this`
had not before v34 -- so the dump is checked for existence and readability
BEFORE any value is believed, and a nonsensical double is reported as such
rather than interpreted.

Usage:  python3 check_v35.py <capture.jsonl>
"""
import json
import struct
import sys
from collections import Counter

path = sys.argv[1] if len(sys.argv) > 1 else "capture.jsonl"

n_rows = n_readable = n_unreadable = 0
vals = Counter()
sizes = Counter()

for line in open(path):
    try:
        d = json.loads(line)
    except Exception:
        continue
    if d.get("kind") != "buffer_dump" or d.get("label") != "icc_scales":
        continue
    n_rows += 1
    if not d.get("readable"):
        n_unreadable += 1
        continue
    b = bytes.fromhex(d.get("hex") or "")
    sizes[len(b)] += 1
    if len(b) < 0x18:
        continue
    n_readable += 1
    # dumped from this+0x110, so +0x118 is at offset 8, +0x120 at offset 0x10
    src = struct.unpack_from("<d", b, 0x08)[0]
    dst = struct.unpack_from("<d", b, 0x10)[0]
    vals[(src, dst)] += 1

print(f"icc_scales rows: {n_rows}   readable: {n_readable}   "
      f"unreadable: {n_unreadable}")
print(f"dump sizes: {dict(sizes)}")

if n_rows == 0:
    sys.exit("FAIL: the icc_scales row never fired -- wrong DLL, or the hook "
             "did not run. Check the injected binary against hookdll_v35.dll "
             "md5 0999feaedde016f04b7eaea001815ec0.")
if n_readable == 0:
    sys.exit("FAIL: icc_scales present but never readable -- this+0x110 "
             "straddles unmapped memory; shrink numBytes and re-run.")

print("\nsource max (+0x118) / dest max (+0x120):")
for (src, dst), k in vals.most_common(8):
    sane = all(0.0 < v < 1e9 for v in (src, dst))
    print(f"   src {src!r:>22}   dst {dst!r:>22}   x{k}"
          f"{'' if sane else '   <-- implausible, treat as wrong offset'}")

src, dst = vals.most_common(1)[0][0]
print()
if abs(src - 4095) < 1:
    print("VERDICT: source max = 4095 -> the x255/4095 encode is CORRECT,")
    print("         and a pipeline stage is MISSING between tone and ICC.")
elif abs(src - 32767) < 1:
    print("VERDICT: source max = 32767 -> the ENCODE is wrong (this port")
    print("         assumes 4095); no stage is missing.")
elif 1000 <= src <= 2500:
    print(f"VERDICT: source max = {src} -- in DRA's paper range (1200..2000).")
    print("         The ENCODE is wrong: it must map the paper domain, not")
    print("         0..4095. No stage is missing.")
else:
    print(f"VERDICT: source max = {src} -- none of the three hypotheses in")
    print("         §135.2. Do not force-fit it; work out what it is.")
