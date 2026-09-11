"""Validate every scalar input §76.4's U/V algorithm reads.

All of these live inside buffer ranges v24 already captured, so they can be
checked now. If they come back as sensible values at the derived offsets,
that is strong evidence the offsets are right and the v25 run will be clean
-- rather than discovering a wrong offset after another hardware round trip.
"""
import json
import struct
from collections import defaultdict

CAP = "/Users/guy/.claude-account-1/jobs/5e3f6f65/tmp/live_hooks_20260817-175818.jsonl"
ev = [json.loads(l) for l in open(CAP) if l.strip()]
du = defaultdict(dict)
for d in ev:
    if d.get("kind") == "buffer_dump":
        du[d["call_id"]][d["label"]] = d

def pick(cid, *labs):
    best = None
    for lab in labs:
        r = du[cid].get(lab)
        if r and r.get("readable"):
            b = bytes.fromhex(r["hex"])
            if best is None or len(b) > len(best):
                best = b
    return best

rows = []
for d in ev:
    if (d.get("kind") == "call" and d.get("event") == "enter"
            and d.get("hook_id") == "sba_order_fpo_calc"):
        sw = d.get("stack_dwords") or []
        if len(sw) >= 13 and int(sw[3], 16) == 0:
            cid = d["call_id"]
            rows.append((cid, pick(cid, "arg2_big", "arg2_388c"),
                         pick(cid, "arg6_big", "arg6_unknown"),
                         pick(cid, "arg7_big", "arg7_3c34"),
                         pick(cid, "arg11_big", "fos_dmin"),
                         pick(cid, "arg0_big", "arg0_dens")))

print(f"{len(rows)} live arg3==0 scenes\n")
print(f"{'scene':>5s} {'Nmin':>6s} {'R1':>6s} {'R2':>6s} {'i8[arg2+4]':>11s} "
      f"{'Ythr':>8s} {'selmask 1s':>11s} {'wtbl min/max':>13s}")
for i, (cid, a2, a6, a7, a11, a0) in enumerate(rows, 1):
    Nmin = struct.unpack_from("<h", a6, 0xDC + 0x12)[0]
    R1 = struct.unpack_from("<h", a6, 0xDC + 0x14)[0]
    R2 = struct.unpack_from("<h", a6, 0xDC + 0x16)[0]
    a2b4 = struct.unpack_from("<b", a2, 4)[0]
    Ythr = struct.unpack_from("<i", a11, 0x48)[0]
    mask = a11[0xC20:0xC20 + 864]
    ones = sum(1 for b in mask if b == 1)
    tbl = a7[:50 * 83]
    w = [struct.unpack_from("<b", tbl, k)[0] for k in range(len(tbl))]
    print(f"{i:5d} {Nmin:6d} {R1:6d} {R2:6d} {a2b4:11d} {Ythr:8d} "
          f"{ones:5d}/{len(mask):<5d} {min(w):6d}/{max(w):<6d}")

print()
print("interpretation checks:")
c = rows[0]
Nmin = struct.unpack_from("<h", c[2], 0xDC + 0x12)[0]
print(f"  Nmin={Nmin} -- a sample-count threshold, must be 0..864: "
      f"{'OK' if 0 <= Nmin <= 864 else 'OUT OF RANGE'}")
tbl = c[3][:50 * 83]
w = [struct.unpack_from('<b', tbl, k)[0] for k in range(len(tbl))]
print(f"  weight table {len(tbl)} bytes, range {min(w)}..{max(w)} -- "
      f"§76.4 says these are percentages: "
      f"{'OK' if -100 <= min(w) and max(w) <= 100 else 'SUSPECT'}")
mask = c[4][0xC20:0xC20 + 864]
print(f"  selection mask: {sorted(set(mask))} distinct byte values -- "
      f"§76.4 tests == 1")
