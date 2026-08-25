#!/usr/bin/env python3
"""Acceptance check for a v36 capture: did the scp_lut_worker rows fire?

docs/74 §142.5: the Unicorn harness runs the real SCPLut worker
(`fcn.10287eb0`) but every reachable path returns identity slopes `[1,1,1]` and
NaN `slopeDist`, because the caller fills the interesting slots from live Impl
state. v36 adds the `scp_lut_worker` hook and the `scpw_arg0/1/2` / `scpw_this`
dumps to capture exactly that.

The rows have NEVER fired before this capture -- same position `bai_this` was in
before v34 and `icc_scales` before v35 -- so existence and readability are
checked BEFORE any value is believed.

Usage:  python3 check_v36.py <capture.jsonl>
"""
import json
import struct
import sys
from collections import Counter

path = sys.argv[1] if len(sys.argv) > 1 else "capture.jsonl"

calls = 0
rows = Counter()
readable = Counter()
sizes = Counter()
this_vals = Counter()
bad = 0

for line in open(path):
    try:
        d = json.loads(line)
    except Exception:
        bad += 1
        continue
    k = d.get("kind")
    if k == "call" and d.get("hook_id") == "scp_lut_worker":
        calls += 1
    elif k == "buffer_dump":
        lab = d.get("label") or ""
        if not lab.startswith("scpw_"):
            continue
        rows[lab] += 1
        if d.get("readable"):
            readable[lab] += 1
            b = bytes.fromhex(d.get("hex") or "")
            sizes[(lab, len(b))] += 1
            if lab == "scpw_this" and len(b) >= 0x50:
                # the caller reads word [esi+0x4a] and byte [esi+0x4e]
                w4a = struct.unpack_from("<h", b, 0x4A)[0]
                b4e = b[0x4E]
                this_vals[(w4a, b4e)] += 1

print(f"unparseable lines            : {bad}")
print(f"scp_lut_worker calls         : {calls}")
print(f"scpw_* dump rows             : {dict(rows)}")
print(f"          readable           : {dict(readable)}")
print(f"          sizes              : {dict(sizes)}")

if calls == 0:
    sys.exit("FAIL: the scp_lut_worker hook never fired. Either the injected "
             "binary is not hookdll_v36.dll (md5 "
             "d8e274d7524eb79d7fa552f5ffb95d99), or SCPLut does not run on "
             "this film path -- which would itself be a finding, since §139.3's "
             "position tension predicts SCPLut is a BALANCE-phase stage.")

if not readable:
    sys.exit("FAIL: scp_lut_worker fired but no scpw_* dump is readable -- "
             "shrink the numBytes on those rows and re-run.")

print()
print("caller-supplied Impl control words (§142.5: word [esi+0x4a], byte [esi+0x4e]):")
for (w, bb), n in this_vals.most_common(8):
    print(f"   word[+0x4a] = {w:6d}   byte[+0x4e] = {bb:3d}   x{n}")

print()
print("PASS -- inputs captured. Next: drive pakon_scp_worker_golden.run_on_planes")
print("with these, and check slopes come back off 1.0 before porting anything.")
