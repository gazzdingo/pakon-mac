"""Test §76's Y derivation against real captured data.

§76: orderFpo.Y = fos_opening_axes(arg5).Y + L[-0x200], and L[-0x200] is
fcn.1028ae00's own arg 9. v24 hooks that function, and the engine logs the
first 16 raw stack dwords per entry -- so arg 9 is in the capture.

fos_opening_axes(879,1250,1386) = (2029, 96, 359)  [port, Unicorn-verified]
"""
import json
import struct
import sys
from collections import defaultdict

sys.path.insert(0, "/Users/guy/www/pakon-mac/.claude/worktrees/tender-gliding-abelson/tools/ansel/python-pipeline")
import pakon_fos as F

CAP = "/Users/guy/.claude-account-1/jobs/5e3f6f65/tmp/live_hooks_20260817-175818.jsonl"
events = [json.loads(l) for l in open(CAP) if l.strip()]
dumps = defaultdict(dict)
for d in events:
    if d.get("kind") == "buffer_dump":
        dumps[d["call_id"]][d["label"]] = d

CONST = F.fos_opening_axes(879, 1250, 1386)
print(f"constant term fos_opening_axes(879,1250,1386) = {CONST}")
print()

def s32(v):
    return v - (1 << 32) if v >= (1 << 31) else v

# Walk the stream: each arg3==0 order_fpo_calc is followed by its helper
# call(s) and then the Preference that observes the result.
pending = None
rows = []
for d in events:
    if d.get("kind") != "call" or d.get("event") != "enter":
        continue
    h = d.get("hook_id")
    if h == "sba_order_fpo_calc":
        sw = d.get("stack_dwords") or []
        if len(sw) >= 13 and int(sw[3], 16) == 0:
            r = dumps[d["call_id"]].get("pref_data_before")
            pending = {"cid": d["call_id"],
                       "pref_addr": r["addr"] if r else None,
                       "helper_args": None}
        else:
            pending = None
    elif h == "sba_order_fpo_helper" and pending is not None:
        sw = d.get("stack_dwords") or []
        if pending["helper_args"] is None:
            pending["helper_args"] = [int(x, 16) for x in sw[:16]]
    elif h == "sba_preference" and pending is not None:
        r = dumps[d["call_id"]].get("pref_data")
        if r and r.get("readable") and r["addr"] == pending["pref_addr"]:
            triple = struct.unpack_from("<hhh", bytes.fromhex(r["hex"]), 0)
            rows.append((pending["cid"], pending["helper_args"], triple))
        pending = None

print(f"{len(rows)} scenes with helper args + observed orderFpo\n")
print(f"{'scene':>5s} {'observed Y':>11s} {'Y-2029 (needed L)':>18s} {'helper arg9':>13s} {'match':>6s}")
ok = 0
for i, (cid, hargs, triple) in enumerate(rows, 1):
    need = triple[0] - CONST[0]
    a9 = s32(hargs[9]) if hargs else None
    m = "YES" if a9 == need else "no"
    if a9 == need:
        ok += 1
    print(f"{i:5d} {triple[0]:11d} {need:18d} {str(a9):>13s} {m:>6s}")
print(f"\narg9 == required L on {ok}/{len(rows)}")

if ok != len(rows) and rows and rows[0][1]:
    print("\nfull 16 stack dwords of the first helper call, signed:")
    for j, v in enumerate(rows[0][1]):
        print(f"   [{j:2d}] {s32(v):12d}  0x{v:08x}")
    print(f"\nrequired L values per scene: {[t[0]-CONST[0] for _,_,t in rows]}")
